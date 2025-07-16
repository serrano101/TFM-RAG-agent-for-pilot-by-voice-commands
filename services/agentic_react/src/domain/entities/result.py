from dataclasses import dataclass

@dataclass
class Result:
    response: str
    steps: list = None  # Lista de pasos de reasoning (opcional)
    success: bool = True
    error: str = None