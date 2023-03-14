from abc import abstractmethod
from asyncio import Queue
from typing import List, Union

from vedro.core import VirtualScenario, VirtualStep

__all__ = ("DevStepScheduler", "PlainStepScheduler", "StepScheduler",)


class StepScheduler:
    def __init__(self, scenario: VirtualScenario) -> None:
        self._scenario = scenario

    @abstractmethod
    def __aiter__(self) -> "StepScheduler":
        pass

    @abstractmethod
    async def __anext__(self) -> VirtualStep:
        pass


class PlainStepScheduler(StepScheduler):
    def __init__(self, scenario: VirtualScenario) -> None:
        super().__init__(scenario)
        self._steps: List[VirtualStep] = []

    def __aiter__(self) -> "PlainStepScheduler":
        self._steps = [step for step in self._scenario.steps]
        return self

    async def __anext__(self) -> VirtualStep:
        if not self._steps:
            raise StopAsyncIteration()
        return self._steps.pop(0)


class DevStepScheduler(StepScheduler):
    def __init__(self, scenario: VirtualScenario) -> None:
        super().__init__(scenario)
        self._queue: Queue[Union[VirtualStep, None]] = Queue()
        for step in scenario.steps:
            self._queue.put_nowait(step)

    def schedule(self, step: Union[VirtualStep, None]) -> None:
        self._queue.put_nowait(step)

    def __aiter__(self) -> "DevStepScheduler":
        return self

    async def __anext__(self) -> VirtualStep:
        maybe_step = await self._queue.get()
        if maybe_step is None:
            raise StopAsyncIteration()
        return maybe_step
