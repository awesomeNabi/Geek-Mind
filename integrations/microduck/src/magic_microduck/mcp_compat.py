"""Narrow SDK 1/2 compatibility boundary for the existing MAGIC MCP client."""

from types import SimpleNamespace

from mcp_servers.client import MCPClientManager


class SessionView:
    def __init__(self, session):
        self.session = session

    async def list_tools(self):
        result = await self.session.list_tools()
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=getattr(tool, "input_schema", getattr(tool, "inputSchema", None)),
                )
                for tool in result.tools
            ]
        )

    async def call_tool(self, *args, **kwargs):
        return await self.session.call_tool(*args, **kwargs)


class CompatibleMCPClientManager(MCPClientManager):
    async def _connect_server(self, config, exit_stack):
        return SessionView(await super()._connect_server(config, exit_stack))
