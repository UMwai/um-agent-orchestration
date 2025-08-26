from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class TaskSpec(BaseModel):
    id: str
    title: str
    description: str
    role: str  # e.g., "backend", "data_analyst", "computational_biologist", "fund_manager"
    acceptance: Dict[str, Any] = Field(default_factory=dict)
    target_dir: str = "."

class TaskStatus(BaseModel):
    id: str
    role: str
    branch: str
    state: str  # "queued" | "running" | "passed" | "failed" | "error"
    last_error: Optional[str] = None