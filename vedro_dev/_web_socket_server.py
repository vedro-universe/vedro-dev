from json import loads
from typing import Any, Awaitable, Callable, Dict, Optional
from weakref import WeakSet

from aiohttp.web import Application, AppRunner, Request, TCPSite, WebSocketResponse

__all__ = ("WebSocketServer", "MessageType",)

MessageType = Dict[str, Any]


class WebSocketServer:
    def __init__(self, host: str = "localhost", port: int = 8084, *,
                 on_connect: Optional[Callable[[], Awaitable[None]]] = None,
                 on_disconnect: Optional[Callable[[], Awaitable[None]]] = None,
                 on_message: Optional[Callable[[MessageType], Awaitable[None]]] = None) -> None:
        self._host = host
        self._port = port

        self._app = Application()
        self._app.router.add_get("/ws", self._handler)
        self._runner = AppRunner(self._app, handle_signals=False)

        self._app["websockets"] = WeakSet()
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_message = on_message

    async def _handler(self, request: Request) -> WebSocketResponse:
        ws = WebSocketResponse()
        await ws.prepare(request)
        request.app["websockets"].add(ws)
        if self._on_connect:
            await self._on_connect()

        try:
            async for msg in ws:
                if self._on_message:
                    await self._on_message(loads(msg.data))
        finally:
            request.app["websockets"].discard(ws)
            if self._on_disconnect:
                await self._on_disconnect()

        return ws

    async def send_message(self, message: Any) -> None:
        for ws in self._app["websockets"]:
            await ws.send_json(message)

    async def start(self) -> None:
        await self._runner.setup()
        site = TCPSite(self._runner, self._host, self._port)
        await site.start()

    async def stop(self) -> None:
        await self._runner.cleanup()
