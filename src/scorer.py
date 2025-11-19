# src/scorer.py
from .models import SimulationState
from .config import COST_WASHER, COST_DRYER

def calculate_net_business_value(state: SimulationState) -> float:
    """
    NBV = Cash + Asset_Value - Debt
    Asset_Value considers the remaining health of the machines.
    """
    asset_value = 0.0
    for m in state.machines:
        base_cost = COST_WASHER if m.type == 'washer' else COST_DRYER
        # If broken, scrap value is low (10%). If working, value is Health * Cost
        val = base_cost * max(0.1, m.health)
        asset_value += val

    nbv = state.cash + asset_value - state.debt
    return round(nbv, 2)
