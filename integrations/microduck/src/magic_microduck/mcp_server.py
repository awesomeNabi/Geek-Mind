"""MCP facade runs in MAGIC's environment and talks to the independent ROS bridge."""

import base64
import functools
from typing import Literal

try:
    from mcp.server.mcpserver import MCPServer as Server, Image
except ImportError:
    from mcp.server.fastmcp import FastMCP as Server, Image

from .client import BridgeClient, BridgeUnavailable
from .contracts import SCHEMAS

try:
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp.exceptions import ToolError

server = Server(
    "microduck",
    instructions=(
        "Simulation controller. submit_action returns acceptance, NOT completion. "
        "Wait for SUCCEEDED using get_action_status before submitting another action. "
        "Use a new observation_token for repeated status polls in MAGIC Cortex. "
        "Do not replay UNKNOWN actions. stop does not interrupt an already running trained skill."
    ),
)
client = BridgeClient()


def bridge_tool(fn):
    """Turn 'nobody is listening' into an actionable tool error instead of a crash."""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except BridgeUnavailable as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


@server.tool()
@bridge_tool
async def get_state() -> dict:
    """Read fresh pose, posture, named rooms, active actions and controller readiness."""
    return await client.state()


@server.tool()
async def get_capabilities() -> dict:
    """Read exact argument schemas for the allowed Microduck skills."""
    return {"skills": SCHEMAS, "trained_skill_cancel_supported": False, "simulation_only": True}


@server.tool()
@bridge_tool
async def submit_action(
    skill: Literal["walk", "turn", "navigate", "navigate_to", "do_skill", "look", "snapshot"],
    arguments: dict,
    command_id: str,
) -> dict:
    """Start one bounded action. Stable command_id prevents replay; return is normally RUNNING."""
    return await client.start(skill, arguments, command_id)


@server.tool()
@bridge_tool
async def get_action_status(command_id: str, observation_token: int = 0) -> dict:
    """Read an existing receipt. Increment observation_token on each poll; never starts movement."""
    return await client.status(command_id)


@server.tool()
@bridge_tool
async def cancel_action(command_id: str) -> dict:
    """Request cancellation; CANCEL_REQUESTED is not yet confirmed. Trained skills cannot be interrupted."""
    return await client.cancel(command_id)


@server.tool()
@bridge_tool
async def stop() -> dict:
    """Request stop for active movement/navigation and publish zero velocity; inspect action receipts."""
    return await client.stop()


@server.tool()
@bridge_tool
async def get_image() -> Image:
    """Return a fresh head-camera JPEG as MCP image content."""
    value = await client.request("/image")
    return Image(data=base64.b64decode(value["base64"]), format="jpeg")


def main():
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
