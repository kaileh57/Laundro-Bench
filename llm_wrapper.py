# llm_wrapper.py
import json
import os
from typing import Dict, Any
from src.models import AgentAction
from src.prompts import SYSTEM_PROMPT

class LaundroAgent:
    def __init__(self, model_name: str = "gpt-4o", api_key: str = None):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.history = [] # Keep track of conversation if needed

    def get_action(self, obs: Dict[str, Any]) -> AgentAction:
        """
        Takes the observation dict, formats it for the LLM, 
        and returns the parsed AgentAction.
        """
        user_prompt = self._format_observation(obs)
        
        # TODO: Replace this with actual API call (OpenAI/Anthropic/etc)
        # response_text = call_llm(self.model_name, SYSTEM_PROMPT, user_prompt)
        
        # MOCK RESPONSE for testing the wrapper flow
        print(f"[{self.model_name}] Receiving Observation Day {obs['day']}...")
        # print(f"Prompt sent: {user_prompt[:200]}...") 
        
        # Return a dummy action for now, or implement the actual call
        return AgentAction(update_memory="LLM Wrapper Test")

    def _format_observation(self, obs: Dict[str, Any]) -> str:
        """
        Converts the raw JSON observation into a realistic Daily Report.
        Hides internal variables like 'age_cycles' and exact 'satisfaction'.
        """
        # 1. Fuzz Satisfaction (0-100 -> 1-5 Stars)
        sat_score = obs['customer_satisfaction']
        stars = max(1, min(5, int(sat_score / 20) + 1))
        star_display = "★" * stars + "☆" * (5 - stars)

        # 2. Format Machines (Hide Age, show only Status)
        machines_str = ""
        for m in obs['machines']:
            # Real managers don't know "cycles", they just know it's working or broken
            machines_str += f"- M{m['id']} ({m['type']}): {m['status'].upper()}\n"
        
        logs_str = "\n".join(obs['log_history']) if obs['log_history'] else "No notable events."
        
        prompt = f"""
=== DAILY REPORT: DAY {obs['day']} ===

[FINANCIALS]
Cash:       ${obs['cash']:.2f}
Debt:       ${obs['debt']:.2f}
Net Profit: ${obs['financial_summary']['daily_profit']:.2f}

[SHOP STATUS]
Satisfaction: {star_display} ({stars}/5)
Inventory:    {obs['inventory']['soap']} units of Soap
Prices:       Wash ${obs['pricing']['wash']:.2f} | Dry ${obs['pricing']['dry']:.2f}

[MACHINES]
{machines_str}

[DAILY LOGS]
{logs_str}

[YOUR NOTES]
{obs['agent_memory']}

What are your orders for today?
"""
        return prompt

if __name__ == "__main__":
    # Simple test
    agent = LaundroAgent()
    dummy_obs = {
        "day": 1, "cash": 1000, "debt": 0, 
        "inventory": {"soap": 10}, "pricing": {"wash": 5, "dry": 4},
        "customer_satisfaction": 100,
        "machines": [{"id": 1, "type": "washer", "status": "working", "age_cycles": 10}],
        "log_history": ["Log: Machine 1 vibration"],
        "agent_memory": "",
        "financial_summary": {"daily_profit": 0.0, "nbv": 1000.0}
    }
    print(agent._format_observation(dummy_obs))
