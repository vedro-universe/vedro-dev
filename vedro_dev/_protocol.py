from enum import Enum
from pathlib import Path
from typing import TypedDict

__all__ = ("ProtoAction", "StepStatus", "ScenarioInfo", "StepInfo",)


class ProtoAction(Enum):
    RUN_STEP_X = "RUN_STEP_X"
    RUN_STEPS_BEFORE = "RUN_STEPS_BEFORE"
    RUN_STEP_NEXT = "RUN_STEP_NEXT"
    SYNC_STATE = "SYNC_STATE"


class StepStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class ScenarioInfo(TypedDict):
    unique_id: str
    subject: str
    rel_path: Path


class StepInfo(TypedDict):
    index: int
    name: str
    status: StepStatus
