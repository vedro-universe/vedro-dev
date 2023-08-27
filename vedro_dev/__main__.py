import asyncio
from argparse import ArgumentParser

from aiohttp import ClientConnectorError, ClientSession
from aiohttp.http_websocket import WSMessage


async def connect(host: str, port: int) -> None:
    async with ClientSession() as session:
        async with session.ws_connect(f"ws://{host}:{port}/ws") as ws:
            async for msg in ws:
                assert isinstance(msg, WSMessage)
                print("Message:", msg)


async def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=8484, type=int)

    args = parser.parse_args()
    try:
        await connect(args.host, args.port)
    except ClientConnectorError as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
