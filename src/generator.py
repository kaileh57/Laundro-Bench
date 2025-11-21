# src/generator.py
import json
import os
import random
from typing import List, Dict, Any

SCENARIO_DIR = "data/scenarios"

SCENARIO_DEFINITIONS = [
    {
        "id": "S-01",
        "name": "The Control",
        "seed": 42,
        "description": "Standard scenario, no tricks",
        "hidden_mechanics": None
    },
    {
        "id": "S-02", 
        "name": "The Lemons",
        "seed": 101,
        "description": "Some machines are defective",
        "hidden_mechanics": {
            "type": "lemon_machines",
            "lemon_ids": [3, 7],
            "degradation_mult": 10.0
        }
    },
    {
        "id": "S-03",
        "name": "The Regime Shift", 
        "seed": 202,
        "description": "Economic conditions change",
        "hidden_mechanics": {
            "type": "regime_shift",
            "shift_day": 180,
            "phase_1": {"demand_mult": 1.0, "cost_mult": 1.0},
            "phase_2": {"demand_mult": 0.5, "cost_mult": 1.3}
        }
    },
    {
        "id": "S-04",
        "name": "The Supply Chain",
        "seed": 303,
        "description": "Unpredictable delivery times",
        "hidden_mechanics": {
            "type": "random_delays",
            "min_delay": 1,
            "max_delay": 21
        }
    },
    {
        "id": "S-05",
        "name": "The Competitor",
        "seed": 404,
        "description": "Competitor responds to your pricing",
        "hidden_mechanics": {
            "type": "adaptive_competitor",
            "response_delay": 7,
            "undercut_amount": 0.50
        }
    },
    {
        "id": "S-06",
        "name": "Cascading Failures",
        "seed": 505,
        "description": "Machine failures affect others",
        "hidden_mechanics": {
            "type": "cascading_failures",
            "load_redistribution": 0.2,
            "spatial_damage": 0.02
        }
    },
    {
        "id": "S-07",
        "name": "The Inspector",
        "seed": 606,
        "description": "Periodic inspections with hidden threshold",
        "hidden_mechanics": {
            "type": "periodic_inspection",
            "interval": 60,
            "threshold": 85,
            "fine": 500
        }
    },
    {
        "id": "S-08",
        "name": "The Fraud",
        "seed": 707,
        "description": "Repair service is unreliable",
        "hidden_mechanics": {
            "type": "repair_fraud",
            "cheap_failure_rate": 0.60,
            "premium_failure_rate": 0.0
        }
    }
]

def ensure_dir():
    if not os.path.exists(SCENARIO_DIR):
        os.makedirs(SCENARIO_DIR)

def generate_scenarios():
    """Generate scenario files WITHOUT revealing hidden mechanics"""
    ensure_dir()
    print(f"Generating {len(SCENARIO_DEFINITIONS)} scenarios in {SCENARIO_DIR}...")
    
    for s_def in SCENARIO_DEFINITIONS:
        scenario_data = {
            "id": s_def['id'],
            "name": s_def['name'],
            "seed": s_def['seed'],
            "description": s_def['description'],
            # DO NOT include hidden_mechanics in the file
            # Engine will load from SCENARIO_SECRETS
            "config_overrides": {} # Empty for now, as mechanics are hidden
        }
        
        fname = os.path.join(SCENARIO_DIR, f"{s_def['id']}.json")
        with open(fname, 'w') as f:
            json.dump(scenario_data, f, indent=2)
            
    print("Done.")

# Secrets - stored separately, never exposed to agent
SCENARIO_SECRETS = {
    s_def['id']: s_def.get('hidden_mechanics')
    for s_def in SCENARIO_DEFINITIONS
}

def get_scenario_secret(scenario_id: str):
    """Get hidden mechanics for a scenario"""
    return SCENARIO_SECRETS.get(scenario_id)

if __name__ == "__main__":
    generate_scenarios()
