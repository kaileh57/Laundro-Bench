# run_llm.py
import sys
import os
import json
import argparse
from src.engine import LaundromatEnv
from src.llm_wrapper import LLMWrapper
from src.diagnostics import Diagnostics
from colorama import Fore, Style, init

init(autoreset=True)

def run_scenario(scenario_id: str, model_name: str, verbose: bool = False):
    print(f"{Fore.CYAN}Running Scenario {scenario_id} with {model_name}{Style.RESET_ALL}")
    
    env = LaundromatEnv(f"data/scenarios/{scenario_id}.json")
    agent = LLMWrapper(model_name=model_name)
    diagnostics = Diagnostics(env.scenario['id'], env.hidden_mechanics)
    
    # Initial Obs
    obs = env._create_observation(env.state)
    
    total_days = 365
    for _ in range(total_days):
        if verbose:
            print(f"Day {obs['day']}: Cash ${obs['cash']}")
            
        try:
            # Get Action from LLM
            action = agent.get_action(obs)
        except NotImplementedError:
            print(f"{Fore.RED}LLM API not configured. Please implement _call_llm in src/llm_wrapper.py{Style.RESET_ALL}")
            return 0
        except Exception as e:
            print(f"{Fore.RED}Error getting action: {e}{Style.RESET_ALL}")
            # Fallback to empty action
            from src.models import AgentAction
            action = AgentAction()

        # Step
        obs = env.step(action)
        diagnostics.record_step(env.state, action, obs['daily_logs'])
        
    # Report
    report = diagnostics.generate_report()
    nbv = obs['_internal_metrics']['nbv']
    
    print(f"{Fore.GREEN}Scenario Complete.{Style.RESET_ALL}")
    print(f"NBV: ${nbv}")
    print(f"Strategy: {report['strategy']}")
    
    return nbv, report

def main():
    parser = argparse.ArgumentParser(description="Run LLM Evaluation on Laundro-Bench")
    parser.add_argument("--model", type=str, default="gemini-pro", help="Model name to use")
    parser.add_argument("--scenario", type=str, default="all", help="Scenario ID or 'all'")
    parser.add_argument("--verbose", action="store_true", help="Print daily status")
    args = parser.parse_args()
    
    scenarios = [
        "S-01", "S-02", "S-03", "S-04", 
        "S-05", "S-06", "S-07", "S-08"
    ]
    
    if args.scenario != "all":
        scenarios = [args.scenario]
        
    results = {}
    
    for s_id in scenarios:
        nbv, report = run_scenario(s_id, args.model, args.verbose)
        results[s_id] = {
            "nbv": nbv,
            "report": report
        }
        
    # Save
    with open("results/llm_eval.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nResults saved to results/llm_eval.json")

if __name__ == "__main__":
    main()
