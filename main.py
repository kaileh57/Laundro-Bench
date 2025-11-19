# main.py
import sys
import random
from src.generator import generate_scenarios
from src.engine import LaundromatEnv
from src.models import AgentAction
from colorama import Fore, Style, init

init(autoreset=True)

def random_agent(obs):
    """
    Agent 1: Random
    A simple baseline agent that acts randomly but sensibly.
    """
    # 1. Check machines
    ops = []
    for m in obs['machines']:
        if m['status'] == 'broken':
            ops.append({'machine_id': m['id'], 'action': 'repair_cheap'})
        elif 'Loud banging' in str(obs['log_history']):
             # Rudimentary text parsing
             if str(m['id']) in str(obs['log_history']):
                 ops.append({'machine_id': m['id'], 'action': 'inspect'})

    # 2. Check Inventory
    buy = {}
    if obs['inventory']['soap'] < 20:
        buy['soap'] = 10
    
    # 3. Random Marketing
    mkt = 0.0
    if random.random() < 0.1:
        mkt = 20.0

    return AgentAction(
        maintenance_ops=ops,
        buy_inventory=buy,
        marketing_change=mkt,
        pricing_change=None,
        update_memory=f"Day {obs['day']} processed."
    )

def reactive_agent(obs):
    """
    Agent 2: Reactive
    - Repairs immediately upon 'broken' status.
    - Buys soap when < 10.
    - Never changes prices.
    - Never does preventive maintenance.
    """
    ops = []
    for m in obs['machines']:
        if m['status'] == 'broken':
            # Always chooses premium to ensure fix
            ops.append({'machine_id': m['id'], 'action': 'repair_premium'})

    buy = {}
    if obs['inventory']['soap'] < 10:
        buy['soap'] = 20 # Buy enough to last a while
    
    return AgentAction(
        maintenance_ops=ops,
        buy_inventory=buy,
        marketing_change=0.0,
        pricing_change=None,
        update_memory="Reactive logic applied."
    )

def greedy_agent(obs):
    """
    Agent 3: Greedy
    - Raises prices constantly.
    - Only does 'Cheap Repairs'.
    - Never spends on marketing.
    - Buys minimum inventory.
    """
    ops = []
    for m in obs['machines']:
        if m['status'] == 'broken':
            ops.append({'machine_id': m['id'], 'action': 'repair_cheap'})

    buy = {}
    if obs['inventory']['soap'] < 5:
        buy['soap'] = 5 # Bare minimum
    
    # Aggressive pricing strategy
    current_wash = obs['pricing']['wash']
    current_dry = obs['pricing']['dry']
    
    # Slowly creep prices up
    new_pricing = None
    if obs['day'] % 10 == 0:
        new_pricing = {
            'wash': current_wash + 0.5,
            'dry': current_dry + 0.5
        }

    return AgentAction(
        maintenance_ops=ops,
        buy_inventory=buy,
        marketing_change=0.0,
        pricing_change=new_pricing,
        update_memory="Greedy logic applied."
    )

def run_simulation(scenario_id="S-01", agent_func=random_agent, total_days=365, verbose=False):
    if verbose:
        print(f"{Fore.CYAN}Initializing Laundro-Bench Scenario: {scenario_id}{Style.RESET_ALL}")
    
    env = LaundromatEnv(f"data/scenarios/{scenario_id}.json")
    
    # Enforce determinism for the agent's random actions
    random.seed(env.seed)
    
    obs = env.state.model_dump() # Initial state
    # Sanitize init
    for m in obs['machines']: del m['health']

    for _ in range(total_days):
        if verbose:
            print(f"\n{Fore.YELLOW}--- DAY {obs['day']} ---{Style.RESET_ALL}")
            print(f"Cash: ${obs['cash']:.2f} | Sat: {obs['customer_satisfaction']:.1f}")
        
        # Agent decides
        action = agent_func(obs)
        
        # Environment steps
        obs = env.step(action)
        
        # Print Logs
        if verbose:
            for log in obs['log_history']:
                if "CRITICAL" in log:
                    print(f"{Fore.RED}{log}{Style.RESET_ALL}")
                elif "Log:" in log:
                    print(f"{Fore.LIGHTBLACK_EX}{log}{Style.RESET_ALL}")
                else:
                    print(log)

    nbv = obs['financial_summary']['nbv']
    if verbose:
        print(f"\n{Fore.GREEN}Simulation Complete.{Style.RESET_ALL}")
        print(f"Final Net Business Value: ${nbv}")
    
    return nbv

import json
import os

def run_baseline():
    print(f"{Fore.MAGENTA}=== STARTING COMPREHENSIVE BASELINE RUN ==={Style.RESET_ALL}")
    generate_scenarios()
    
    if not os.path.exists("results"):
        os.makedirs("results")

    scenarios = [
        "S-01", "S-01-Hard",
        "S-02", "S-02-Hard",
        "S-03", "S-03-Hard",
        "S-04", "S-04-Hard",
        "S-05", "S-05-Hard",
        "S-06", "S-06-Hard",
        "S-07", "S-07-Hard",
        "S-08", "S-08-Hard"
    ]
    
    agents = {
        "Random": random_agent,
        "Reactive": reactive_agent,
        "Greedy": greedy_agent
    }
    
    print(f"{'Scenario':<20} | {'Random':<15} | {'Reactive':<15} | {'Greedy':<15}")
    print("-" * 70)
    
    agent_results = {name: {} for name in agents}

    for s_id in scenarios:
        print(f"{s_id:<20} | ", end="", flush=True)
        for name, func in agents.items():
            try:
                nbv = run_simulation(s_id, agent_func=func, total_days=365, verbose=False)
                color = Fore.GREEN if nbv > 0 else Fore.RED
                print(f"{color}${nbv:,.0f}{Style.RESET_ALL}".ljust(24), end="")
                agent_results[name][s_id] = nbv
            except Exception as e:
                print(f"{Fore.RED}ERROR{Style.RESET_ALL}".ljust(24), end="")
                agent_results[name][s_id] = None
        print()
    
    # Save Results
    for name, data in agent_results.items():
        with open(f"results/{name}.json", "w") as f:
            json.dump(data, f, indent=2)
    print(f"\n{Fore.CYAN}Results saved to results/ directory.{Style.RESET_ALL}")

if __name__ == "__main__":
    # Check if user wants a specific single run or the full baseline
    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        run_simulation(verbose=True)
    else:
        run_baseline()
