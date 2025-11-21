# src/engine.py
import json
import numpy as np
from typing import Dict, Any, List, Optional
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
        
        # Track maintenance history for observation
        self._maintenance_history = {}  # {machine_id: last_maintenance_day}
        
        # Track yesterday's stats
        self._yesterday_customers = 0
        self._yesterday_turnaway = 0
        self._yesterday_revenue = 0.0

        # Load hidden mechanics (not in scenario file)
        from .generator import get_scenario_secret
        self.hidden_mechanics = get_scenario_secret(self.scenario['id'])
        
        self.state = self._initialize_state()
        
        # Initialize hidden mechanic state
        self._init_hidden_mechanics()

    def _init_hidden_mechanics(self):
        """Initialize state for hidden mechanics"""
        if not self.hidden_mechanics:
            return
            
        mech_type = self.hidden_mechanics.get('type')
        
        if mech_type == 'adaptive_competitor':
            self.competitor_prices = {'wash': 5.0, 'dry': 4.0}
            self.last_competitor_update = 0
            
        elif mech_type == 'cascading_failures':
            self.cascade_log = []  # Track cascade events

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
                self.pending_orders.append((arrival, item, qty))
                logs.append(f"ORDER: Bought {qty} {item} for ${cost}. Arrival Day {arrival}.")

        # 2.5 Process Inspections (NEW)
        for inspection in action.inspections:
            m = next((x for x in self.state.machines if x.id == inspection.machine_id), None)
            if not m:
                logs.append(f"ERROR: Machine {inspection.machine_id} not found")
                continue
                
            cost = 10.0
            if self.state.cash >= cost:
                self.state.cash -= cost
                
                # Reveal health range (not exact value)
                health_pct = m.health * 100
                if health_pct >= 80:
                    condition = "EXCELLENT"
                    estimate = "80-100%"
                elif health_pct >= 60:
                    condition = "GOOD"
                    estimate = "60-80%"
                elif health_pct >= 40:
                    condition = "FAIR"
                    estimate = "40-60%"
                elif health_pct >= 20:
                    condition = "POOR"
                    estimate = "20-40%"
                else:
                    condition = "CRITICAL"
                    estimate = "0-20%"
                
                # Estimate remaining cycles (fuzzy)
                remaining = (m.health * 2000) if m.age_cycles < 2000 else (m.health * 1000)
                remaining_low = int(remaining * 0.8)
                remaining_high = int(remaining * 1.2)
                
                logs.append(
                    f"INSPECT: Machine {m.id} | Condition: {condition} ({estimate}) | "
                    f"Est. Remaining Life: {remaining_low}-{remaining_high} cycles"
                )
            else:
                logs.append(f"INSPECT: Insufficient funds (need $10)")

        # 3. Process Maintenance
        for op in action.maintenance_ops:
            m = next((x for x in self.state.machines if x.id == op.machine_id), None)
            if not m: continue

            cost = 0
            if op.action == 'inspect':
                # Deprecated in favor of dedicated inspection action, but kept for backward compatibility if needed
                # or we can remove it. The new design uses action.inspections.
                # Let's remove it from here to enforce using the new field?
                # Or just map it? Let's ignore it here and rely on the new loop below.
                pass
                # cost = 10
                # # Inspection reveals true health via log
                # logs.append(f"INSPECT: Machine {m.id} Health is {m.health:.2f}")
            
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
            
            # Track maintenance for observation
            if op.action in ['repair_cheap', 'repair_premium', 'replace']:
                self._maintenance_history[op.machine_id] = self.state.day

        # 4. Process Event Tape
        events = self.event_tape.get(str(self.state.day), [])
        demand_override = None
        
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
        
        # Track yesterday's stats for observation
        self._yesterday_customers = actual_washes
        self._yesterday_turnaway = lost_customers
        self._yesterday_revenue = income
        
        # Generate sanitized observation
        obs = self._create_observation(self.state)
        
        # Add financial summary (not part of observation)
        obs['_internal_metrics'] = {  # Prefix with _ to indicate not for agent
            'daily_profit': round(daily_profit, 2),
            'nbv': calculate_net_business_value(self.state),
            'true_satisfaction': self.state.customer_satisfaction  # For our analysis
        }
        
        return obs

    def _apply_hidden_mechanics(self):
        """Apply scenario-specific hidden mechanics"""
        if not self.hidden_mechanics:
            return
            
        mech = self.hidden_mechanics
        mech_type = mech.get('type')
        
        if mech_type == 'lemon_machines':
            self._apply_lemon_logic(mech)
            
        elif mech_type == 'regime_shift':
            self._apply_regime_shift(mech)
            
        elif mech_type == 'adaptive_competitor':
            self._apply_competitor_logic(mech)
            
        elif mech_type == 'cascading_failures':
            self._apply_cascade_logic(mech)
            
        elif mech_type == 'periodic_inspection':
            self._apply_inspection_logic(mech)
            
        elif mech_type == 'repair_fraud':
            # Handled during repair processing
            pass

    def _apply_lemon_logic(self, mech):
        """Machines degrade faster if they're lemons"""
        lemon_ids = mech['lemon_ids']
        mult = mech['degradation_mult']
        
        for m in self.state.machines:
            if m.id in lemon_ids and m.status == 'working':
                # Extra degradation for lemons
                extra_deg = calculate_degradation(m, self.rng, mult)
                m.health -= extra_deg

    def _apply_regime_shift(self, mech):
        """Economic conditions change at specific day"""
        shift_day = mech['shift_day']
        
        if self.state.day == shift_day:
            self.state.log_history.append("NEWS: Economic conditions changing in the area")
        
        if self.state.day >= shift_day:
            # Apply phase 2 multipliers
            phase_2 = mech['phase_2']
            self.utility_cost_mult = phase_2['cost_mult']
            self.config['base_demand_mult'] = phase_2['demand_mult']

    def _apply_competitor_logic(self, mech):
        """Competitor adapts prices with delay"""
        response_delay = mech['response_delay']
        undercut = mech['undercut_amount']
        
        if self.state.day % response_delay == 0:
            # Competitor updates prices based on yours
            if self.state.pricing['wash'] > 5.5:
                self.competitor_prices['wash'] = self.state.pricing['wash'] - undercut
                self.state.log_history.append("RUMOR: Competitor across street changed prices")
            elif self.state.pricing['wash'] < 4.5:
                self.competitor_prices['wash'] = self.state.pricing['wash']
                
            # Similar for dryer
            if self.state.pricing['dry'] > 4.5:
                self.competitor_prices['dry'] = self.state.pricing['dry'] - undercut
            elif self.state.pricing['dry'] < 3.5:
                self.competitor_prices['dry'] = self.state.pricing['dry']
            
            # If competitor is cheaper, demand drops
            if self.competitor_prices['wash'] < self.state.pricing['wash']:
                self.config['competitor_active'] = True # Triggers demand drop in calculate_demand
            else:
                self.config['competitor_active'] = False

    def _apply_cascade_logic(self, mech):
        """Broken machines cause others to fail faster"""
        load_mult = mech['load_redistribution']
        spatial_dmg = mech['spatial_damage']
        
        broken = [m for m in self.state.machines if m.status == 'broken']
        working = [m for m in self.state.machines if m.status == 'working']
        
        if not broken:
            return
            
        # Cascade 1: Load redistribution
        # Working machines degrade faster when others are broken
        for m in working:
            extra_load = len(broken) * load_mult
            m.health -= (calculate_degradation(m, self.rng) * extra_load)
        
        # Cascade 2: Spatial damage
        # Adjacent machines to broken ones take damage
        for broken_m in broken:
            adjacent_ids = [broken_m.id - 1, broken_m.id + 1]
            for adj_id in adjacent_ids:
                adj_m = next((m for m in working if m.id == adj_id), None)
                if adj_m:
                    adj_m.health -= spatial_dmg
                    if self.rng.random() < 0.3:
                        self.state.log_history.append(
                            f"Observation: Machine {adj_id} showing signs of wear "
                            f"(near broken Machine {broken_m.id})"
                        )

    def _apply_inspection_logic(self, mech):
        """Periodic inspections with hidden threshold"""
        interval = mech['interval']
        threshold = mech['threshold']
        fine = mech['fine']
        
        if self.state.day % interval == 0:
            if self.state.customer_satisfaction < threshold:
                self.state.cash -= fine
                self.state.log_history.append(f"HEALTH INSPECTION: FAILED - Fine: ${fine}")
                self.state.log_history.append("Customers report unsatisfactory conditions")
            else:
                self.state.log_history.append("HEALTH INSPECTION: PASSED")

    def _create_observation(self, state: SimulationState) -> Dict[str, Any]:
        """
        Generate properly sanitized observation.
        Agent should ONLY see what a real manager would see.
        """
        obs = {
            'day': state.day,
            'cash': self._add_accounting_noise(state.cash),
            'debt': state.debt,
            'inventory': state.inventory.copy(),
            'pricing': state.pricing.copy(),
            'machines': self._sanitize_machines(state.machines),
            'daily_logs': state.log_history[-10:],  # Only recent logs
            'satisfaction_stars': self._satisfaction_to_stars(state.customer_satisfaction),
            'agent_memory': state.agent_memory,
            'yesterday_stats': {
                'customers_served': self._yesterday_customers,
                'customers_turned_away': self._yesterday_turnaway,
                'revenue': self._yesterday_revenue
            }
        }
        
        # Remove raw state data
        # NO health, NO age_cycles, NO exact satisfaction
        
        return obs

    def _sanitize_machines(self, machines: List[Machine]) -> List[Dict]:
        """Remove ALL hidden information from machines"""
        sanitized = []
        for m in machines:
            # Only reveal what visual inspection shows
            info = {
                'id': m.id,
                'type': m.type,
                'status': m.status,  # 'working' or 'broken'
                'last_maintenance_day': self._maintenance_history.get(m.id, 0),
                'days_since_maintenance': self.state.day - self._maintenance_history.get(m.id, 0)
            }
            sanitized.append(info)
        return sanitized

    def _satisfaction_to_stars(self, satisfaction: float) -> int:
        """Convert exact satisfaction to fuzzy star rating"""
        # 0-100 -> 1-5 stars with intentional fuzziness
        if satisfaction >= 90: return 5
        elif satisfaction >= 75: return 4
        elif satisfaction >= 55: return 3
        elif satisfaction >= 35: return 2
        else: return 1

    def _add_accounting_noise(self, value: float) -> float:
        """Add ±5% accounting uncertainty to financial data"""
        noise = self.rng.uniform(-0.05, 0.05)
        return round(value * (1 + noise), 2)
