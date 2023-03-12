import sys
from time import time
from typing import AsyncIterator, Callable, Tuple, Type, Union

from vedro import Scenario
from vedro.core import (
    Dispatcher,
    ExcInfo,
    Report,
    ScenarioResult,
    ScenarioRunner,
    ScenarioScheduler,
    StepResult,
    VirtualScenario,
    VirtualStep,
)
from vedro.core.scenario_runner import Interrupted
from vedro.events import (
    ExceptionRaisedEvent,
    ScenarioFailedEvent,
    ScenarioPassedEvent,
    ScenarioReportedEvent,
    ScenarioRunEvent,
    ScenarioSkippedEvent,
    StepFailedEvent,
    StepPassedEvent,
    StepRunEvent,
)

from ._step_scheduler import PlainStepScheduler, StepScheduler

__all__ = ("DevScenarioRunner",)

StepSchedulerType = Union[Type[StepScheduler],
                          Callable[[VirtualScenario], AsyncIterator[VirtualStep]]]


class DevScenarioRunner(ScenarioRunner):
    def __init__(self, dispatcher: Dispatcher, *,
                 interrupt_exceptions: Tuple[Type[BaseException], ...] = (),
                 step_scheduler: StepSchedulerType = PlainStepScheduler) -> None:
        super().__init__()
        self._dispatcher = dispatcher
        assert isinstance(interrupt_exceptions, tuple)
        self._interrupt_exceptions = interrupt_exceptions + (Interrupted,)
        self._step_scheduler = step_scheduler

    async def run_step(self, step: VirtualStep, ref: Scenario) -> StepResult:
        step_result = StepResult(step)

        await self._dispatcher.fire(StepRunEvent(step_result))
        step_result.set_started_at(time())
        try:
            if step.is_coro():
                await step(ref)
            else:
                step(ref)
        except:  # noqa: E722
            step_result.set_ended_at(time()).mark_failed()

            exc_info = ExcInfo(*sys.exc_info())
            await self._dispatcher.fire(ExceptionRaisedEvent(exc_info))
            step_result.set_exc_info(exc_info)

            await self._dispatcher.fire(StepFailedEvent(step_result))
        else:
            step_result.set_ended_at(time()).mark_passed()
            await self._dispatcher.fire(StepPassedEvent(step_result))

        return step_result

    async def run_scenario(self, scenario: VirtualScenario) -> ScenarioResult:
        scenario_result = ScenarioResult(scenario)

        if scenario.is_skipped():
            scenario_result.mark_skipped()
            await self._dispatcher.fire(ScenarioSkippedEvent(scenario_result))
            return scenario_result

        await self._dispatcher.fire(ScenarioRunEvent(scenario_result))
        scenario_result.set_started_at(time())

        ref = scenario()
        scenario_result.set_scope(ref.__dict__)

        async for step in self._step_scheduler(scenario):
            step_result = await self.run_step(step, ref)
            scenario_result.add_step_result(step_result)

        scenario_result.set_ended_at(time())

        for step_result in scenario_result.step_results:
            if step_result.is_failed():
                scenario_result.mark_failed()
                await self._dispatcher.fire(ScenarioFailedEvent(scenario_result))
                return scenario_result

        scenario_result.mark_passed()
        await self._dispatcher.fire(ScenarioPassedEvent(scenario_result))
        return scenario_result

    async def _run_scenarios(self, scheduler: ScenarioScheduler, report: Report) -> None:
        async for scenario in scheduler:
            scenario_result = await self.run_scenario(scenario)
            aggregated_result = scheduler.aggregate_results([scenario_result])
            report.add_result(aggregated_result)
            await self._dispatcher.fire(ScenarioReportedEvent(aggregated_result))

    async def run(self, scheduler: ScenarioScheduler) -> Report:
        report = Report()
        try:
            await self._run_scenarios(scheduler, report)
        except self._interrupt_exceptions:
            exc_info = ExcInfo(*sys.exc_info())
            report.set_interrupted(exc_info)
        return report
