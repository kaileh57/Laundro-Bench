# src/models.py
from typing import Literal, Dict, List, Optional
from pydantic import BaseModel, Field

class Machine(BaseModel):
    id: int
    type: Literal['washer', 'dryer']
    status: Literal['working', 'broken', 'maintenance'] = 'working'
    age_cycles: int = 0
    health: float = 1.0  # Hidden from agent
    efficiency: float = 1.0

class SimulationState(BaseModel):
    day: int
    cash: float
    debt: float
    inventory: Dict[str, int]  # 'soap', 'machine_parts'
    pricing: Dict[str, float]  # 'wash', 'dry'
    marketing_spend: float
    customer_satisfaction: float = 100.0
    machines: List[Machine]
    log_history: List[str] = []
    agent_memory: str = ""

class MaintenanceOp(BaseModel):
    machine_id: int
    action: Literal['inspect', 'repair_cheap', 'repair_premium', 'replace']

class AgentAction(BaseModel):
    pricing_change: Optional[Dict[str, float]] = None
    buy_inventory: Optional[Dict[str, int]] = None # {'soap': 5, 'machine_parts': 1}
    maintenance_ops: List[MaintenanceOp] = []
    marketing_change: Optional[float] = None
    pay_debt: float = 0.0
    update_memory: Optional[str] = None
