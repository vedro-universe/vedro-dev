from enum import Enum
from pathlib import Path
from typing import TypedDict

__all__ = ("Action", "StepStatus", "ScenarioInfo", "StepInfo",)


class Action(Enum):
    RUN_SPECIFIC_STEP = "RunSecificStep"
    RUN_TO_STEP = "RunToStep"
    RUN_NEXT_STEP = "RunNextStep"
    UPDATE_STATE = "UpdateState"


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
