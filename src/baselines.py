# src/baselines.py
import random
from typing import Dict, Any
from .models import AgentAction

class SmartAgent:
    def __init__(self):
        self.machine_estimates = {} # {id: estimated_health}
        self.last_inspection = {} # {id: day}
        self.pricing_strategy = {'wash': 5.0, 'dry': 4.0}
        
    def act(self, obs: Dict[str, Any]) -> AgentAction:
        day = obs['day']
        
        # 1. Update Estimates based on logs
        self._update_estimates(obs)
        
        # 2. Maintenance Logic
        ops = []
        inspections = []
        
        for m in obs['machines']:
            m_id = m['id']
            status = m['status']
            
            # Estimate health decay
            if m_id in self.machine_estimates:
                self.machine_estimates[m_id] -= 0.005 # Daily decay estimate
            else:
                self.machine_estimates[m_id] = 1.0
                
            # Critical Repair
            if status == 'broken':
                ops.append({'machine_id': m_id, 'action': 'repair_premium'})
                self.machine_estimates[m_id] = 1.0
                continue
                
            # Preventive Maintenance
            est_health = self.machine_estimates[m_id]
            if est_health < 0.4:
                ops.append({'machine_id': m_id, 'action': 'repair_cheap'})
                self.machine_estimates[m_id] += 0.3
            
            # Inspection Strategy (Information Gathering)
            # Inspect if uncertain and machine is old/suspicious
            days_since_check = day - self.last_inspection.get(m_id, 0)
            if days_since_check > 30 and obs['cash'] > 100:
                inspections.append({'machine_id': m_id})
                self.last_inspection[m_id] = day

        # 3. Inventory Logic
        buy = {}
        soap = obs['inventory']['soap']
        if soap < 50:
            buy['soap'] = 50
            
        # 4. Pricing Logic (Supply/Demand)
        # If yesterday was full, raise price. If empty, lower.
        y_stats = obs.get('yesterday_stats', {})
        if y_stats.get('customers_turned_away', 0) > 5:
            self.pricing_strategy['wash'] += 0.25
        elif y_stats.get('customers_served', 0) < 10:
            self.pricing_strategy['wash'] = max(2.0, self.pricing_strategy['wash'] - 0.25)
            
        return AgentAction(
            maintenance_ops=ops,
            inspections=inspections,
            buy_inventory=buy,
            pricing_change=self.pricing_strategy,
            marketing_change=10.0 if obs['cash'] > 1000 else 0.0,
            update_memory=f"Smart Agent: Est Health {self.machine_estimates}"
        )

    def _update_estimates(self, obs):
        for log in obs['daily_logs']:
            # Parse inspection results
            if "INSPECT: Machine" in log:
                try:
                    parts = log.split("|")
                    m_part = parts[0].strip() # INSPECT: Machine X
                    m_id = int(m_part.split()[-1])
                    cond_part = parts[1].strip() # Condition: GOOD (60-80%)
                    
                    if "EXCELLENT" in cond_part: val = 0.9
                    elif "GOOD" in cond_part: val = 0.7
                    elif "FAIR" in cond_part: val = 0.5
                    elif "POOR" in cond_part: val = 0.3
                    elif "CRITICAL" in cond_part: val = 0.1
                    else: val = 0.5
                    
                    self.machine_estimates[m_id] = val
                except:
                    pass
            
            # Parse symptoms
            if "Loud banging" in log:
                # Find machine id? The log format is "Loud banging heard from Machine X"
                try:
                    m_id = int(log.split("Machine ")[-1].strip("."))
                    self.machine_estimates[m_id] = min(self.machine_estimates.get(m_id, 1.0), 0.3)
                except:
                    pass

# Wrapper for main.py compatibility
_smart_agent_instance = SmartAgent()
def smart_agent_wrapper(obs):
    return _smart_agent_instance.act(obs)
