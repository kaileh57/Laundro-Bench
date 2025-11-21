# src/llm_wrapper.py
import json
import re
from typing import Dict, Any, List
from .models import AgentAction
from .prompts import SYSTEM_PROMPT

class LLMWrapper:
    def __init__(self, model_name: str = "gemini-pro"):
        self.model_name = model_name
        self.memory = [] # List of message dicts
        self.system_prompt = SYSTEM_PROMPT
        
    def get_action(self, obs: Dict[str, Any]) -> AgentAction:
        """
        Main entry point.
        1. Format observation
        2. Send to LLM
        3. Parse response
        4. Return AgentAction
        """
        user_prompt = self._format_observation(obs)
        
        # In a real implementation, this would call the API
        # response_text = self._call_llm(user_prompt)
        
        # For now, we will raise NotImplementedError as this requires an actual API key/client
        # Or we can return a dummy action for testing integration
        # return AgentAction()
        
        raise NotImplementedError("LLM API call not implemented. User must provide API client.")

    def _format_observation(self, obs: Dict[str, Any]) -> str:
        """Convert observation dict to readable text for the LLM"""
        
        # Financials
        fin = f"Day: {obs['day']}\n"
        fin += f"Cash: ${obs['cash']}\n"
        fin += f"Debt: ${obs['debt']}\n"
        fin += f"Satisfaction: {obs['satisfaction_stars']} Stars\n"
        
        # Machines
        machines = "Machines:\n"
        for m in obs['machines']:
            machines += f"- ID {m['id']} ({m['type']}): {m['status'].upper()}"
            if 'days_since_maint' in m:
                machines += f" (Last Maint: {m['days_since_maint']} days ago)"
            machines += "\n"
            
        # Logs
        logs = "Daily Logs:\n"
        for log in obs['daily_logs']:
            logs += f"- {log}\n"
            
        # Memory
        mem = f"Your Notes: {obs.get('agent_memory', 'None')}\n"
        
        return f"{fin}\n{machines}\n{logs}\n{mem}\nWhat are your decisions for today?"

    def _parse_response(self, response_text: str) -> AgentAction:
        """Extract JSON from response and validate"""
        try:
            # Find JSON block
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                json_str = match.group(0)
                data = json.loads(json_str)
                return AgentAction(**data)
            else:
                # Fallback: Try to parse entire string
                data = json.loads(response_text)
                return AgentAction(**data)
        except Exception as e:
            print(f"Error parsing LLM response: {e}")
            # Return empty action (do nothing) on error
            return AgentAction()

    def _call_llm(self, prompt: str) -> str:
        """
        Placeholder for actual API call.
        User should implement this with their preferred provider (OpenAI, Anthropic, Google).
        """
        pass
