from dataclasses import dataclass

@dataclass
class Query:
    text: str
    metadata: dict = None