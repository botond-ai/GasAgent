from dataclasses import dataclass

@dataclass(frozen=True)
class Participant:
    name: str
    age: int = 0
