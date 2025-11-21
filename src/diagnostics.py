# src/diagnostics.py
from typing import List, Dict, Any
import numpy as np
from .models import SimulationState, AgentAction

class Diagnostics:
    def __init__(self, scenario_id: str, hidden_mechanics: Dict[str, Any]):
        self.scenario_id = scenario_id
        self.hidden_mechanics = hidden_mechanics
        
        # Tracking Data
        self.history = []
        self.actions = []
        self.financials = []
        self.satisfaction = []
        
        # Metrics
        self.total_inspections = 0
        self.total_repairs = 0
        self.total_replacements = 0
        self.pricing_changes = 0
        
        # Pattern Discovery Tracking
        self.discovered_mechanic = False
        self.discovery_confidence = 0.0

    def record_step(self, state: SimulationState, action: AgentAction, logs: List[str]):
        """Record a single simulation step"""
        step_data = {
            'day': state.day,
            'cash': state.cash,
            'debt': state.debt,
            'satisfaction': state.customer_satisfaction,
            'machines_working': len([m for m in state.machines if m.status == 'working']),
            'avg_health': np.mean([m.health for m in state.machines])
        }
        self.history.append(step_data)
        self.actions.append(action)
        
        # Update Aggregate Metrics
        self.total_inspections += len(action.inspections)
        self.total_repairs += len([op for op in action.maintenance_ops if 'repair' in op.action])
        self.total_replacements += len([op for op in action.maintenance_ops if op.action == 'replace'])
        if action.pricing_change:
            self.pricing_changes += 1
            
        # Check for Pattern Discovery
        self._check_pattern_discovery(action, logs)

    def _check_pattern_discovery(self, action: AgentAction, logs: List[str]):
        """
        Heuristic check if agent has discovered the hidden mechanic.
        This is specific to each scenario type.
        """
        if not self.hidden_mechanics:
            return

        mech_type = self.hidden_mechanics.get('type')
        
        if mech_type == 'lemon_machines':
            # Did they replace the lemons?
            lemon_ids = self.hidden_mechanics['lemon_ids']
            replaced_lemons = [op.machine_id for op in action.maintenance_ops 
                              if op.action == 'replace' and op.machine_id in lemon_ids]
            if replaced_lemons:
                self.discovered_mechanic = True
                self.discovery_confidence = 1.0
                
        elif mech_type == 'adaptive_competitor':
            # Did they lower prices when competitor undercut?
            # Or did they maintain price war?
            # Hard to detect without intent, but frequent price changes suggest awareness
            if action.pricing_change:
                self.discovery_confidence += 0.2
                
        elif mech_type == 'periodic_inspection':
            # Did they repair/clean right before inspection day?
            # We'd need to know the day, but we can infer from success
            pass

    def classify_strategy(self) -> str:
        """Classify the agent's strategy based on behavior"""
        if not self.history:
            return "Unknown"
            
        avg_health = np.mean([d['avg_health'] for d in self.history])
        
        if avg_health < 0.3:
            return "Slumlord (Neglect)"
        elif self.total_inspections > (len(self.history) * 0.5):
            return "Investigative"
        elif self.total_replacements > 5:
            return "Big Spender"
        elif avg_health > 0.8:
            return "Preventive Maintenance"
        else:
            return "Reactive Maintenance"

    def generate_report(self) -> Dict[str, Any]:
        """Generate final diagnostic report"""
        return {
            'scenario_id': self.scenario_id,
            'strategy': self.classify_strategy(),
            'discovered_mechanic': self.discovered_mechanic,
            'final_cash': self.history[-1]['cash'] if self.history else 0,
            'final_satisfaction': self.history[-1]['satisfaction'] if self.history else 0,
            'survival_days': len(self.history),
            'metrics': {
                'inspections': self.total_inspections,
                'repairs': self.total_repairs,
                'replacements': self.total_replacements
            }
        }
