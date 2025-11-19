# src/engine.py
import json
import numpy as np
from typing import Dict, Any
from .models import SimulationState, Machine, AgentAction
from .config import *
from .mechanics import calculate_degradation, generate_logs, calculate_demand
from .scorer import calculate_net_business_value

class LaundromatEnv:
    def __init__(self, scenario_file: str):
        with open(scenario_file, 'r') as f:
            self.scenario = json.load(f)
        
        self.seed = self.scenario['seed']
        self.rng = np.random.RandomState(self.seed)
        self.config = self.scenario['config_overrides']
        self.event_tape = self.scenario.get('event_tape', {})
        
        self.utility_cost_mult = 1.0
        self.soap_lead_time = 14 if self.config.get('supply_shock') else 1
        self.pending_orders = [] # List of (arrival_day, type, amount)

        self.state = self._initialize_state()

    def _initialize_state(self) -> SimulationState:
        # S-06 Slumlord Override
        is_slumlord = self.config.get('slumlord_start', False)
        cash = self.config.get('initial_cash', 500.0 if is_slumlord else INITIAL_CASH)
        debt = self.config.get('initial_debt', 10000.0 if is_slumlord else INITIAL_DEBT)
        
        machines = []
        for i in range(1, 11):
            m_type = 'washer' if i <= 6 else 'dryer'
            
            # S-02 Lemon Law Override
            start_age = 50 if self.config.get('lemon_law') else 0
            start_health = 1.0
            status = 'working'

            if is_slumlord and i % 2 == 0:
                status = 'broken'
                start_health = 0.0
                start_age = 3000

            machines.append(Machine(
                id=i, type=m_type, status=status, 
                age_cycles=start_age, health=start_health
            ))

        return SimulationState(
            day=1,
            cash=cash,
            debt=debt,
            inventory={'soap': INITIAL_SOAP, 'machine_parts': INITIAL_PARTS},
            pricing={'wash': PRICE_WASH, 'dry': PRICE_DRY},
            marketing_spend=0.0,
            machines=machines
        )

    def step(self, action: AgentAction) -> Dict[str, Any]:
        logs = []
        
        # 1. Update Configs / Memory
        if action.pricing_change:
            self.state.pricing.update(action.pricing_change)
        if action.update_memory:
            self.state.agent_memory = action.update_memory
        if action.marketing_change is not None:
            self.state.marketing_spend = action.marketing_change

        # 2. Financial Transactions
        # Pay Debt
        if action.pay_debt > 0:
            if self.state.cash >= action.pay_debt:
                self.state.cash -= action.pay_debt
                self.state.debt = max(0, self.state.debt - action.pay_debt)
                logs.append(f"FINANCE: Paid ${action.pay_debt} towards debt.")
            else:
                logs.append("FINANCE: Transaction Declined (Insufficient Funds for Debt).")

        # Buy Inventory
        if action.buy_inventory:
            for item, qty in action.buy_inventory.items():
                cost = 0
                if item == 'soap': cost = qty * COST_SOAP_UNIT
                elif item == 'machine_parts': cost = qty * COST_PART
                
                # Allow Overdraft (Debt financing)
                self.state.cash -= cost
                arrival = self.state.day + self.soap_lead_time if item == 'soap' else self.state.day + 1
                self.pending_orders.append((arrival, item, qty))
                logs.append(f"ORDER: Bought {qty} {item} for ${cost}. Arrival Day {arrival}.")

        # 3. Process Maintenance
        for op in action.maintenance_ops:
            m = next((x for x in self.state.machines if x.id == op.machine_id), None)
            if not m: continue

            cost = 0
            if op.action == 'inspect':
                cost = 10
                # Inspection reveals true health via log
                logs.append(f"INSPECT: Machine {m.id} Health is {m.health:.2f}")
            
            elif op.action == 'repair_cheap':
                cost = COST_REPAIR_CHEAP * self.config.get('repair_cost_mult', 1.0)
                
                # S-08 Grifter Logic
                success = True
                if self.config.get('grifter_repairs'):
                    prob = self.config.get('grift_prob', 0.30)
                    if self.rng.random() < prob: success = False
                
                if success:
                    m.status = 'working'
                    m.health = min(1.0, m.health + 0.3)
                    logs.append(f"MAINT: Machine {m.id} cheap repair completed.")
                else:
                    logs.append(f"MAINT: Machine {m.id} cheap repair FAILED (Grifter scenario).")
                
                self.state.cash -= cost

            elif op.action == 'repair_premium':
                cost = COST_REPAIR_PREMIUM * self.config.get('repair_cost_mult', 1.0)
                m.status = 'working'
                m.health = 1.0
                logs.append(f"MAINT: Machine {m.id} premium repair fully restored.")
                self.state.cash -= cost

            elif op.action == 'replace':
                cost_m = COST_WASHER if m.type == 'washer' else COST_DRYER
                m.age_cycles = 0
                m.health = 1.0
                m.status = 'working'
                self.state.cash -= cost_m
                logs.append(f"MAINT: Machine {m.id} replaced brand new.")
            
            if cost > 0 and op.action != 'replace': # Replace deducted above
                 # Deduct cost (already done in blocks? No, wait. 
                 # In original code, 'replace' deducted inside block. 
                 # 'repair' blocks didn't deduct inside block in original? 
                 # Let's check original lines 110-124. 
                 # Original: if cash >= cost: ... else: declined.
                 # It seems original code deducted at line 148?
                 # "if cost > 0 ... self.state.cash -= cost"
                 # My replacements above ADDED "self.state.cash -= cost".
                 # So I should remove this block to avoid double counting.
                 pass

        # 4. Receive Inventory
        arrived_orders = [o for o in self.pending_orders if o[0] <= self.state.day]
        for _, item, qty in arrived_orders:
            self.state.inventory[item] += qty
            logs.append(f"DELIVERY: Received {qty} {item}.")
        self.pending_orders = [o for o in self.pending_orders if o[0] > self.state.day]

        # 5. Physics & Simulation (The Day Passes)

        # Process Event Tape (Pre-Physics)
        str_day = str(self.state.day)
        demand_override = None

        if str_day in self.event_tape:
            events = self.event_tape[str_day]
            logs.extend(events)
            for e in events:
                if "Rent Hike" in e:
                    self.config['rent_mult'] = self.config.get('rent_mult', 1.0) * 1.10
                elif "FACTORY RECALL" in e:
                    for m in self.state.machines:
                        m.status = 'broken'
                        m.health = 0.0
                elif "Competitor" in e:
                    self.config['competitor_active'] = True
                elif "Health Inspector" in e:
                    if self.state.customer_satisfaction < 90:
                        self.state.cash -= 500
                        logs.append("FINE: Failed health inspection! -$500")
                elif "Loan Shark" in e:
                    self.state.cash -= 500
                elif "Power Outage" in e:
                    demand_override = 0
                    logs.append("CRITICAL: Power outage. 0 customers served.")
                elif "Scammer" in e:
                    self.state.cash -= 200
                elif "Theft" in e:
                    self.state.inventory['soap'] = int(self.state.inventory['soap'] * 0.5)
        
        # S-03 Inflation Check
        inflation_interval = self.config.get('inflation_interval', 7)
        if self.config.get('hyper_inflation') and self.state.day % inflation_interval == 0:
            self.utility_cost_mult *= 1.10
            logs.append(f"MACRO: Inflation spike! Utilities now {self.utility_cost_mult:.2f}x base.")

        # S-07 Heatwave Demand
        base_d_val = self.rng.randint(20, 40)
        if self.config.get('heatwave'): base_d_val *= 3
        
        # Apply Base Demand Multiplier (S-01 Hard)
        base_d_val = int(base_d_val * self.config.get('base_demand_mult', 1.0))

        demand = calculate_demand(base_d_val, self.state.pricing, 
                                  self.state.customer_satisfaction, self.rng, self.config)
        
        if demand_override is not None:
            demand = demand_override
        
        working_washers = len([m for m in self.state.machines if m.type == 'washer' and m.status == 'working'])
        working_dryers = len([m for m in self.state.machines if m.type == 'dryer' and m.status == 'working'])
        

        # Throughput
        max_cycles = MAX_CYCLES_PER_DAY
        if self.config.get('water_rationing'):
             max_cycles = int(max_cycles * 0.5)
             logs.append("MACRO: Water rationing in effect. Max cycles reduced.")

        max_wash_loads = working_washers * max_cycles
        max_dry_loads = working_dryers * max_cycles
        
        actual_washes = min(demand, max_wash_loads)
        # Demand for dryers is correlated to washes
        actual_dries = min(actual_washes, max_dry_loads)
        
        lost_customers = demand - actual_washes
        
        # Consume Resources
        soap_needed = actual_washes * SOAP_PER_LOAD
        if self.state.inventory['soap'] < soap_needed:
            # Can't wash without soap
            actual_washes = int(self.state.inventory['soap'] / SOAP_PER_LOAD)
            actual_dries = min(actual_washes, actual_dries)
            logs.append("CRITICAL: Ran out of soap! Turning away customers.")
            lost_customers += (demand - actual_washes)
            self.state.inventory['soap'] = 0
        else:
            self.state.inventory['soap'] -= int(soap_needed) # Integer approximation for inventory
            
        # Financials (Income & Expenses)
        income = (actual_washes * self.state.pricing['wash']) + (actual_dries * self.state.pricing['dry'])
        utility_bill = (actual_washes + actual_dries) * COST_UTILITY_PER_LOAD * self.utility_cost_mult
        
        daily_profit = income - utility_bill - (RENT_DAILY * self.config.get('rent_mult', 1.0)) - self.state.marketing_spend
        self.state.cash += daily_profit

        # Interest on Debt / Overdraft
        interest_rate = self.config.get('interest_rate', 0.001) # 0.1% daily default
        
        # 1. Interest on formal Debt
        if self.state.debt > 0:
            interest = self.state.debt * interest_rate
            self.state.debt += interest
            # logs.append(f"FINANCE: Debt interest charged ${interest:.2f}")

        # 2. Interest on Overdraft (Negative Cash)
        if self.state.cash < 0:
            overdraft_interest = abs(self.state.cash) * (interest_rate * 2) # Higher rate for overdraft
            self.state.cash -= overdraft_interest
            # logs.append(f"FINANCE: Overdraft interest charged ${overdraft_interest:.2f}")
        
        # Degrade Machines
        deg_mult = self.config.get('degradation_mult', 1.0)
        for m in self.state.machines:
            if m.status == 'working':
                cycles = int(actual_washes / working_washers) if m.type == 'washer' and working_washers > 0 else 0
                if m.type == 'dryer' and working_dryers > 0:
                    cycles = int(actual_dries / working_dryers)
                
                m.age_cycles += cycles
                deg = calculate_degradation(m, self.rng, deg_mult) * cycles
                m.health -= deg
                
                # Check Failure
                log_lines = generate_logs(m, self.rng)
                logs.extend(log_lines)

        # Satisfaction Update
        sat_change = 0
        if lost_customers > 0: sat_change -= (lost_customers * 0.5)
        if self.state.machines[0].health < 0.5: sat_change -= 1 # Dirty store penalty
        sat_change += (self.state.marketing_spend / 10.0) # Marketing boost
        
        self.state.customer_satisfaction = max(0.0, min(100.0, self.state.customer_satisfaction + sat_change))

        # Process Event Tape (Post-Physics - Legacy removal, moved to Pre-Physics)
        # Keeping this empty to maintain flow if needed, but logic moved up for "Power Outage" to work

        # Final State Update
        self.state.day += 1
        self.state.log_history = logs
        
        # Construct Observation (Filtering hidden data)
        obs = self.state.model_dump()
        # Sanitize machines
        for m_dat in obs['machines']:
            del m_dat['health']
        
        obs['financial_summary'] = {
            'daily_profit': round(daily_profit, 2),
            'nbv': calculate_net_business_value(self.state)
        }
        
        return obs
