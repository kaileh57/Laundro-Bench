# src/generator.py
import json
import os
import random
from typing import List, Dict, Any

SCENARIO_DIR = "data/scenarios"

SCENARIO_DEFINITIONS = [
    {"id": "S-01", "name": "The Control", "seed": 42, "config": {}},
    {"id": "S-01-Hard", "name": "The Control (Hard)", "seed": 420, "config": {"rent_mult": 2.0, "base_demand_mult": 0.8}},
    
    {"id": "S-02", "name": "The Lemon Law", "seed": 101, "config": {"lemon_law": True, "degradation_mult": 4.0}},
    {"id": "S-02-Hard", "name": "The Lemon Law (Hard)", "seed": 1010, "config": {"lemon_law": True, "degradation_mult": 8.0, "repair_cost_mult": 1.5}},

    {"id": "S-03", "name": "Hyper-Inflation", "seed": 202, "config": {"hyper_inflation": True}},
    {"id": "S-03-Hard", "name": "Hyper-Inflation (Hard)", "seed": 2020, "config": {"hyper_inflation": True, "inflation_interval": 3}},

    {"id": "S-04", "name": "Supply Shock", "seed": 303, "config": {"supply_shock": True}},
    {"id": "S-04-Hard", "name": "Supply Shock (Hard)", "seed": 3030, "config": {"supply_shock": True, "lead_time": 21, "theft_prob": 0.2}},

    {"id": "S-05", "name": "Gentrification", "seed": 404, "config": {"gentrification_strict": True, "high_tolerance": True}},
    {"id": "S-05-Hard", "name": "Gentrification (Hard)", "seed": 4040, "config": {"gentrification_strict": True, "satisfaction_threshold": 95, "price_sensitivity": 2.0}},

    {"id": "S-06", "name": "The Slumlord", "seed": 505, "config": {"slumlord_start": True, "interest_rate": 0.005}},
    {"id": "S-06-Hard", "name": "The Slumlord (Hard)", "seed": 5050, "config": {"slumlord_start": True, "initial_debt": 50000, "initial_cash": 0, "interest_rate": 0.01}},

    {"id": "S-07", "name": "The Heatwave", "seed": 606, "config": {"heatwave": True, "degradation_mult": 2.0}},
    {"id": "S-07-Hard", "name": "The Heatwave (Hard)", "seed": 6060, "config": {"heatwave": True, "degradation_mult": 4.0, "water_rationing": True}},

    {"id": "S-08", "name": "The Grifter", "seed": 707, "config": {"grifter_repairs": True}},
    {"id": "S-08-Hard", "name": "The Grifter (Hard)", "seed": 7070, "config": {"grifter_repairs": True, "grift_prob": 0.9}},
]

def ensure_dir():
    if not os.path.exists(SCENARIO_DIR):
        os.makedirs(SCENARIO_DIR)

def generate_scenarios():
    ensure_dir()
    print(f"Generating {len(SCENARIO_DEFINITIONS)} scenarios in {SCENARIO_DIR}...")
    
    for s_def in SCENARIO_DEFINITIONS:
        # Base event tape (empty for now, but can be populated)
        event_tape: Dict[int, List[str]] = {}
        
        # Scenario specific event injection
        rng = random.Random(s_def['seed'])
        
        # S-04 Supply Shock
        if s_def['config'].get('supply_shock'):
            prob = s_def['config'].get('theft_prob', 0.05)
            for day in range(1, 366):
                if rng.random() < prob:
                    event_tape[day] = ["EVENT: Inventory Theft! Lost 50% of soap."]

        # S-01-Hard: Rent Hikes
        if s_def['id'] == "S-01-Hard":
            for day in [90, 180, 270]:
                event_tape[day] = ["EVENT: Landlord raised rent by 10%."]
        
        # S-02-Hard: Factory Recall (Mass Breakdown)
        if s_def['id'] == "S-02-Hard":
            if rng.random() < 0.5:
                day = rng.randint(100, 200)
                event_tape[day] = ["EVENT: FACTORY RECALL! All machines flagged for defects."]

        # S-03-Hard: Competitor Price War
        if s_def['id'] == "S-03-Hard":
            for day in range(50, 350, 50):
                event_tape[day] = ["EVENT: Competitor opened across street! Demand drops unless prices cut."]

        # S-05-Hard: Health Inspection
        if s_def['id'] == "S-05-Hard":
            for day in range(30, 360, 60):
                event_tape[day] = ["EVENT: Health Inspector incoming! Fine if satisfaction < 90."]

        # S-06-Hard: Loan Shark
        if s_def['id'] == "S-06-Hard":
            for day in range(1, 366, 30):
                event_tape[day] = ["EVENT: Loan Shark demands interest payment ($500)."]

        # S-07-Hard: Power Outage
        if s_def['id'] == "S-07-Hard":
            for day in range(1, 366):
                if rng.random() < 0.02: # 2% chance per day
                    event_tape[day] = ["EVENT: Power Outage! No business today."]

        # S-08-Hard: Scam Artist
        if s_def['id'] == "S-08-Hard":
             for day in range(1, 366):
                if rng.random() < 0.03:
                    event_tape[day] = ["EVENT: Scammer sued for 'slip and fall'. Cash settlement paid."]

        scenario_data = {
            "id": s_def['id'],
            "name": s_def['name'],
            "seed": s_def['seed'],
            "config_overrides": s_def['config'],
            "event_tape": event_tape
        }
        
        fname = os.path.join(SCENARIO_DIR, f"{s_def['id']}.json")
        with open(fname, 'w') as f:
            json.dump(scenario_data, f, indent=2)
            
    print("Done.")

if __name__ == "__main__":
    generate_scenarios()
