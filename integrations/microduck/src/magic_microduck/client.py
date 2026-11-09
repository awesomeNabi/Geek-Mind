"""Small async HTTP client; no ROS dependencies in the MAGIC interpreter."""

import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, build_opener, ProxyHandler

from .settings import URL


class BridgeError(RuntimeError):
    def __init__(self, payload):
        super().__init__(payload.get("detail", payload.get("error", "Bridge error")))
        self.payload = payload


class BridgeUnavailable(BridgeError):
    """The bridge is not listening: a startup-order problem, not a code bug."""

    def __init__(self, url, reason):
        super().__init__(
            {
                "error": "bridge_unavailable",
                "detail": (
                    f"Bridge not reachable at {url} ({reason}). Start the simulator and bridge "
                    "first: run `bash run.sh up` in another terminal and wait for READY."
                ),
            }
        )
        self.url = url


class BridgeClient:
    def __init__(self, url=URL):
        self.url = url.rstrip("/")
        # Local bridge traffic must not go through a user's HTTP proxy.
        self.opener = build_opener(ProxyHandler({}))

    def request_sync(self, path, data=None):
        request = Request(
            self.url + path,
            data=json.dumps(data, allow_nan=False).encode() if data is not None else None,
            headers={"Content-Type": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=20 if path == "/reset" else 8) as response:
                return json.load(response)
        except HTTPError as exc:
            raise BridgeError(json.load(exc)) from exc
        except URLError as exc:
            # Nobody is listening: the simulator/bridge was not started, or already exited.
            raise BridgeUnavailable(self.url, exc.reason) from exc

    async def request(self, path, data=None):
        return await asyncio.to_thread(self.request_sync, path, data)

    async def state(self):
        return await self.request("/state")

    def frame_sync(self, view="head"):
        with self.opener.open(self.url + "/frame.jpg?view=" + quote(view), timeout=3) as response:
            return response.read(), float(response.headers["X-Observed-At"])

    async def start(self, skill, arguments, command_id=None):
        return await self.request("/actions", dict(skill=skill, arguments=arguments, command_id=command_id))

    async def status(self, command_id):
        return await self.request("/actions/" + quote(command_id, safe=""))

    async def cancel(self, command_id):
        return await self.request("/cancel", {"command_id": command_id})

    async def stop(self):
        return await self.request("/stop", {})
