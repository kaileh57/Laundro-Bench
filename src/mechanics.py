# src/mechanics.py
import numpy as np
from typing import List
from .models import Machine

def calculate_degradation(machine: Machine, rng: np.random.RandomState, multiplier: float = 1.0) -> float:
    """
    The Bathtub Curve Logic.
    Returns the amount of health to subtract.
    """
    base_degradation = 0.001  # Base wear per cycle
    
    # 1. Infant Mortality (< 100 cycles)
    if machine.age_cycles < 100:
        # Higher chance of defect spikes
        if rng.random() < 0.05:
            return 0.05 * multiplier
        return base_degradation * multiplier

    # 2. Reliable Middle (100 - 2000 cycles)
    elif machine.age_cycles <= 2000:
        # Very low degradation, random catastrophic failure rare
        if rng.random() < 0.0005: # 0.05% chance
            return 0.10 * multiplier
        return base_degradation * multiplier

    # 3. Wear-Out (> 2000 cycles)
    else:
        # Exponential degradation
        age_factor = (machine.age_cycles - 2000) / 1000.0
        wear = base_degradation * (1.0 + age_factor**2)
        return wear * multiplier

def generate_logs(machine: Machine, rng: np.random.RandomState) -> List[str]:
    """
    Generate VAGUE, symptom-based logs.
    Agent must infer problems, not get diagnoses.
    """
    logs = []
    h = machine.health
    m_id = machine.id

    if h <= 0.0:
        # Only say it failed, not why
        logs.append(f"CRITICAL: Machine {m_id} has stopped working")
        machine.status = 'broken'
        return logs

    # Symptoms get worse as health decreases
    # But we intentionally make them vague and probabilistic
    
    if h < 0.2:
        if rng.random() < 0.70:  # 70% chance of symptom
            symptoms = [
                f"Customer complaint: Machine {m_id} left clothes soaking wet",
                f"Customer complaint: Machine {m_id} didn't clean properly",
                f"Loud banging noise from Machine {m_id} area",
                f"Machine {m_id} vibrating excessively during cycle"
            ]
            logs.append(rng.choice(symptoms))
            
    elif h < 0.4:
        if rng.random() < 0.50:
            symptoms = [
                f"Customer: Machine {m_id} took longer than usual",
                f"Observation: Machine {m_id} sounds louder than normal",
                f"Customer: Clothes from Machine {m_id} smell musty",
            ]
            logs.append(rng.choice(symptoms))
            
    elif h < 0.6:
        if rng.random() < 0.25:
            symptoms = [
                f"Machine {m_id} cycle completed slower than expected",
                f"Minor leak observed near Machine {m_id}",
            ]
            logs.append(rng.choice(symptoms))
            
    elif h < 0.8:
        if rng.random() < 0.10:
            logs.append(f"Machine {m_id} making slight unusual noise")
            
    return logs

def calculate_demand(base_demand: int, 
                     pricing: dict, 
                     satisfaction: float, 
                     rng: np.random.RandomState,
                     scenario_config: dict) -> int:
    """
    Calculates daily customer demand.
    """
    from .config import FAIR_MARKET_WASH, FAIR_MARKET_DRY

    # Price sensitivity
    sensitivity = scenario_config.get('price_sensitivity', 1.0)
    price_penalty = 0.0
    if pricing['wash'] > FAIR_MARKET_WASH:
        price_penalty += (pricing['wash'] - FAIR_MARKET_WASH) * 10 * sensitivity
    if pricing['dry'] > FAIR_MARKET_DRY:
        price_penalty += (pricing['dry'] - FAIR_MARKET_DRY) * 10 * sensitivity
    
    # Satisfaction modifier
    sat_threshold = scenario_config.get('satisfaction_threshold', 80)
    sat_modifier = 1.0
    if satisfaction < 50:
        sat_modifier = 0.5
    elif satisfaction < sat_threshold and scenario_config.get('gentrification_strict', False):
        sat_modifier = 0.0 # Gentrification scenario rule

    # Random flux
    flux = rng.randint(-5, 6)

    demand = int((base_demand - price_penalty + flux) * sat_modifier)
    
    # Competitor Effect (S-03-Hard)
    if scenario_config.get('competitor_active', False):
        demand = int(demand * 0.70) # 30% drop due to competitor

    return max(0, demand)
