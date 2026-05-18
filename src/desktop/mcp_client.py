"""MCP client wrapper for Claudy.

Reads servers from ~/.claudy/mcp_servers.json:
{
  "servers": {
    "filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/tmp"]},
    "github":     {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-github"], "env": {"GITHUB_TOKEN": "..."}}
  }
}
"""
import asyncio
import json
import os


def _config_path():
    return os.path.join(os.path.expanduser("~"), ".claudy", "mcp_servers.json")


def load_servers():
    path = _config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f).get("servers", {})
    except Exception:
        return {}


async def _list_tools_async(server_name, server_cfg):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(
        command=server_cfg.get("command", ""),
        args=server_cfg.get("args", []),
        env={**os.environ, **server_cfg.get("env", {})},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return [
                {"name": t.name, "description": (t.description or "")[:200]}
                for t in tools.tools
            ]


async def _call_tool_async(server_name, server_cfg, tool_name, arguments):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(
        command=server_cfg.get("command", ""),
        args=server_cfg.get("args", []),
        env={**os.environ, **server_cfg.get("env", {})},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            chunks = []
            for c in (result.content or []):
                text = getattr(c, "text", None) or str(c)
                chunks.append(text)
            return "\n".join(chunks) or "(sin salida)"


def list_servers():
    servers = load_servers()
    if not servers:
        return "Sin servidores MCP configurados. Edita ~/.claudy/mcp_servers.json"
    return "Servers:\n" + "\n".join(f"- {n}" for n in servers.keys())


def list_tools(server_name):
    servers = load_servers()
    if server_name not in servers:
        return f"Server '{server_name}' no esta en mcp_servers.json"
    try:
        tools = asyncio.run(_list_tools_async(server_name, servers[server_name]))
        if not tools:
            return "Sin tools."
        return "\n".join(f"- {t['name']}: {t['description']}" for t in tools)
    except Exception as e:
        return f"Error: {e}"


def call_tool(server_name, tool_name, arguments=None):
    servers = load_servers()
    if server_name not in servers:
        return f"Server '{server_name}' no existe."
    try:
        return asyncio.run(_call_tool_async(server_name, servers[server_name], tool_name, arguments or {}))
    except Exception as e:
        return f"Error: {e}"
