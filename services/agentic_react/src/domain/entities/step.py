
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class Step:
    thought: str
    action: str
    observation: Optional[str] = None
    tool_used: Optional[str] = None
    tool_input: Optional[Any] = None
    tool_output: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)