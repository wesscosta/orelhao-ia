from dataclasses import dataclass


@dataclass(slots=True)
class Metrics:
    sessions_started: int = 0
    turns_completed: int = 0
    errors: int = 0
