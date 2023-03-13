from asyncio import CancelledError
from pathlib import Path
from typing import Dict, List, Type, Union, cast

from vedro.core import (
    ConfigType,
    Dispatcher,
    Plugin,
    PluginConfig,
    ScenarioDiscoverer,
    ScenarioLoader,
    ScenarioScheduler,
    VirtualScenario,
    VirtualStep,
)
from vedro.events import (
    ArgParsedEvent,
    ArgParseEvent,
    CleanupEvent,
    ConfigLoadedEvent,
    ScenarioFailedEvent,
    ScenarioPassedEvent,
    ScenarioRunEvent,
    StartupEvent,
    StepFailedEvent,
    StepPassedEvent,
    StepRunEvent,
)

from ._dev_runner import DevScenarioRunner
from ._protocol import ProtoAction, ScenarioInfo, StepInfo, StepStatus
from ._step_scheduler import DevStepScheduler
from ._version import version
from ._web_socket_server import MessageType, WebSocketServer

__all__ = ("VedroDev", "VedroDevPlugin")


class VedroDevPlugin(Plugin):
    def __init__(self, config: Type["VedroDev"]) -> None:
        super().__init__(config)
        self._host = config.host
        self._port = config.port
        self._app_open_on_startup = config.app_open_on_startup
        self._app_url = config.app_url

        self._global_config: ConfigType = cast(ConfigType, ...)
        self._loader: ScenarioLoader = cast(ScenarioLoader, ...)
        self._discoverer: ScenarioDiscoverer = cast(ScenarioDiscoverer, ...)

        self._ws_server: WebSocketServer = cast(WebSocketServer, ...)

        self._scn_scheduler: ScenarioScheduler = cast(ScenarioScheduler, ...)
        self._step_scheduler: DevStepScheduler = cast(DevStepScheduler, ...)
        self._scenario: ScenarioInfo = cast(ScenarioInfo, ...)
        self._steps: Dict[str, StepInfo] = {}

    def _set_scenario(self, scenario: VirtualScenario) -> None:
        self._scenario = {
            "unique_id": scenario.unique_id,
            "subject": scenario.subject,
            "rel_path": scenario.rel_path,
        }

    def _set_steps(self, steps: List[VirtualStep]) -> None:
        updated_steps: Dict[str, StepInfo] = {}
        for index, step in enumerate(steps):
            updated_steps[step.name] = {
                "index": index,
                "name": step.name,
                "status": StepStatus.PENDING,
            }
        self._steps = updated_steps

    def subscribe(self, dispatcher: Dispatcher) -> None:
        self._dispatcher = dispatcher
        self._dispatcher.listen(ConfigLoadedEvent, self.on_config_loaded) \
                        .listen(ArgParseEvent, self.on_arg_parse) \
                        .listen(ArgParsedEvent, self.on_arg_parsed)

    def on_config_loaded(self, event: ConfigLoadedEvent) -> None:
        self._global_config = event.config

    def on_arg_parse(self, event: ArgParseEvent) -> None:
        group = event.arg_parser.add_argument_group("Dev")
        group.add_argument("--dev", action="store_true", help="Enable dev mode")

    def on_arg_parsed(self, event: ArgParsedEvent) -> None:
        if not event.args.dev:
            return

        self._dispatcher.listen(StartupEvent, self.on_startup) \
                        .listen(ScenarioRunEvent, self.on_scenario_run) \
                        .listen(StepRunEvent, self.on_step_run) \
                        .listen(StepPassedEvent, self.on_step_end) \
                        .listen(StepFailedEvent, self.on_step_end) \
                        .listen(ScenarioPassedEvent, self.on_scenario_end) \
                        .listen(ScenarioFailedEvent, self.on_scenario_end) \
                        .listen(CleanupEvent, self.on_cleanup)

        self._loader = self._global_config.Registry.ScenarioLoader()
        self._discoverer = self._global_config.Registry.ScenarioDiscoverer()

        interrupt_exceptions = (KeyboardInterrupt, SystemExit, CancelledError,)
        self._global_config.Registry.ScenarioRunner.register(
            lambda: DevScenarioRunner(self._global_config.Registry.Dispatcher(),
                                      interrupt_exceptions=interrupt_exceptions,
                                      step_scheduler=self._make_step_scheduler),
            self
        )

    def _make_step_scheduler(self, scenario: VirtualScenario) -> DevStepScheduler:
        self._step_scheduler = DevStepScheduler(scenario)
        return self._step_scheduler

    async def _on_connect(self) -> None:
        await self._sync_state()

    async def _run_step_x(self, step_name: str) -> None:
        step = await self._reload_step(self._scenario["unique_id"], self._scenario["rel_path"], step_name)
        self._steps[step.name]["status"] = StepStatus.PENDING
        self._step_scheduler.schedule(step)

    async def _run_step_before(self, step_name: str) -> None:
        reloaded = await self._reload_scenario(self._scenario["unique_id"], self._scenario["rel_path"])
        steps = []
        for step in reloaded.steps:
            steps.append(step)
            if step.name == step_name:
                break
        scenario = VirtualScenario(reloaded._orig_scenario, steps)

        self._set_scenario(scenario)
        self._set_steps(reloaded.steps)

        self._scn_scheduler.schedule(scenario)
        self._step_scheduler.schedule(None)

    async def _run_step_next(self, step_name: Union[str, None]) -> None:
        if step_name is not None:
            return await self._run_step_x(step_name)

        reloaded = await self._reload_scenario(self._scenario["unique_id"], self._scenario["rel_path"])
        steps = [step for idx, step in enumerate(reloaded.steps) if idx == 0]
        scenario = VirtualScenario(reloaded._orig_scenario, steps)

        self._set_scenario(scenario)
        self._set_steps(reloaded.steps)

        if len(steps) == 0:
            return await self._sync_state()
        return await self._run_step_before(steps[0].name)

    async def _on_message(self, message: MessageType) -> None:
        action = ProtoAction(message["action"])
        if action == ProtoAction.RUN_STEP_X:
            await self._run_step_x(message["payload"]["step"])
        elif action == ProtoAction.RUN_STEPS_BEFORE:
            await self._run_step_before(message["payload"]["step"])
        elif action == ProtoAction.RUN_STEP_NEXT:
            await self._run_step_next(message["payload"]["step"])
        else:
            exit(f"Unknown action {action}")

    async def _sync_state(self) -> None:
        steps = []
        for step in self._steps.values():
            steps.append({
                "index": step["index"],
                "name": step["name"],
                "status": step["status"].value,
            })
        await self._ws_server.send_message({
            "action": ProtoAction.SYNC_STATE.value,
            "version": version,
            "payload": {
                "unique_id": self._scenario["unique_id"],
                "subject": self._scenario["subject"],
                "rel_path": str(self._scenario["rel_path"]),
                "steps": sorted(steps, key=lambda x: x["index"]),  # type: ignore
            },
        })

    async def _reload_scenario(self, unique_id: str, rel_path: Path) -> VirtualScenario:
        loaded = await self._loader.load(rel_path)
        scenarios = [VirtualScenario(scn, self._discoverer._discover_steps(scn)) for scn in loaded]  # type: ignore

        candidates = [scn for scn in scenarios if scn.unique_id == unique_id]
        if len(candidates) < 1:
            exit(f"Failed to find scenario {rel_path}")
        return candidates[0]

    async def _reload_step(self, unique_id: str, rel_path: Path, step_name: str) -> VirtualStep:
        scenario = await self._reload_scenario(unique_id, rel_path)

        candidates = [step for step in scenario.steps if step.name == step_name]
        if len(candidates) < 1:
            exit(f"Failed to find step {step_name}")
        return candidates[0]

    async def on_startup(self, event: StartupEvent) -> None:
        self._scn_scheduler = event.scheduler

        scheduled_scenarios = list(self._scn_scheduler.scheduled)
        if len(scheduled_scenarios) != 1:
            exit("Only one scenario can be scheduled in dev mode")

        scheduled = scheduled_scenarios[0]
        scenario = VirtualScenario(scheduled._orig_scenario, [])
        self._set_scenario(scenario)
        self._set_steps(scheduled.steps)

        self._scn_scheduler.ignore(scheduled)
        self._scn_scheduler.schedule(scenario)

        self._ws_server = WebSocketServer(self._host, self._port,
                                          on_connect=self._on_connect,
                                          on_message=self._on_message)
        await self._ws_server.start()

        if self._app_open_on_startup:
            import webbrowser
            webbrowser.open(self._app_url, new=2)  # open new browser page ("tab")

    async def on_scenario_run(self, event: ScenarioRunEvent) -> None:
        pass

    async def on_step_run(self, event: StepRunEvent) -> None:
        self._steps[event.step_result.step_name]["status"] = StepStatus.RUNNING
        await self._sync_state()

    async def on_step_end(self, event: Union[StepPassedEvent, StepFailedEvent]) -> None:
        step_result = event.step_result
        status = StepStatus.FAILED if isinstance(event, StepFailedEvent) else StepStatus.PASSED
        self._steps[step_result.step_name]["status"] = status
        await self._sync_state()

    async def on_scenario_end(self, event: Union[ScenarioPassedEvent, ScenarioFailedEvent]) -> None:
        pass

    async def on_cleanup(self, event: CleanupEvent) -> None:
        await self._ws_server.stop()


class VedroDev(PluginConfig):
    plugin = VedroDevPlugin

    # Host for WebSocket server
    host: str = "0.0.0.0"

    # Port for WebSocket server
    port: int = 8080

    # App URL
    app_url: str = "http://localhost:3000"

    # Open app on startup
    app_open_on_startup: bool = False
