"""Tests del cliente MCP stdio (core/mcp_client.py).

Incluye un servidor MCP FALSO real (subproceso Python hablando JSON-RPC
por stdio) para probar el handshake, tools/list y tools/call de verdad.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.mcp_client import MCPServer, MCPMixin  # noqa: E402

FAKE_SERVER = r"""
import sys, json
def send(o):
    sys.stdout.write(json.dumps(o) + "\n"); sys.stdout.flush()
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    m, i = msg.get("method"), msg.get("id")
    if m == "initialize":
        send({"jsonrpc": "2.0", "id": i, "result": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "serverInfo": {"name": "fake-mcp", "version": "1.0"}}})
    elif m == "tools/list":
        send({"jsonrpc": "2.0", "id": i, "result": {"tools": [
            {"name": "echo", "description": "repite el texto",
             "inputSchema": {"type": "object",
                             "properties": {"text": {"type": "string"}},
                             "required": ["text"]}}]}})
    elif m == "tools/call":
        args = msg["params"]["arguments"]
        if args.get("text") == "explota":
            send({"jsonrpc": "2.0", "id": i,
                  "error": {"code": -1, "message": "boom controlado"}})
        else:
            send({"jsonrpc": "2.0", "id": i, "result": {
                "content": [{"type": "text", "text": "ECO: " + args.get("text", "")}]}})
    elif i is not None:
        send({"jsonrpc": "2.0", "id": i,
              "error": {"code": -32601, "message": "method not found"}})
"""

FAKE_CMD = [sys.executable, "-u", "-c", FAKE_SERVER]


class TestMCPServerReal(unittest.TestCase):
    """Cliente contra un subproceso stdio de verdad."""

    def setUp(self):
        self.srv = MCPServer("fake", FAKE_CMD)
        self.info = self.srv.start(timeout=20)

    def tearDown(self):
        self.srv.close()

    def test_handshake_y_tools(self):
        self.assertEqual(self.info.get("name"), "fake-mcp")
        self.assertTrue(self.srv.alive)
        self.assertEqual(len(self.srv.tools), 1)
        self.assertEqual(self.srv.tools[0]["name"], "echo")

    def test_call_tool(self):
        out = self.srv.call_tool("echo", {"text": "hola claudy"})
        self.assertEqual(out, "ECO: hola claudy")

    def test_error_del_servidor_se_propaga(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.srv.call_tool("echo", {"text": "explota"})
        self.assertIn("boom controlado", str(ctx.exception))

    def test_close_mata_el_proceso(self):
        self.srv.close()
        self.assertFalse(self.srv.alive)


class FakePet(MCPMixin):
    TOOL_REGISTRY = {}

    def __init__(self, servers_cfg):
        self._cfg = servers_cfg
        self.TOOL_REGISTRY = {}

    def _mcp_config(self):
        return self._cfg

    def register_tool(self, name, handler, description, parameters=None):
        self.TOOL_REGISTRY[name] = {"handler": handler,
                                    "description": description,
                                    "schema": parameters}

    def _debug_log(self, *a):
        pass


class TestMixin(unittest.TestCase):
    def setUp(self):
        self.pet = FakePet({"fake": {"command": FAKE_CMD}})

    def tearDown(self):
        for srv in getattr(self.pet, "_mcp_servers", {}).values():
            srv.close()

    def test_conectar_registra_tools(self):
        out = self.pet._mcp_connect("fake")
        self.assertIn("Conectado", out)
        self.assertIn("mcp_fake_echo", self.pet.TOOL_REGISTRY)
        handler = self.pet.TOOL_REGISTRY["mcp_fake_echo"]["handler"]
        self.assertEqual(handler(self.pet, text="ping"), "ECO: ping")

    def test_servidor_inexistente(self):
        self.assertIn("No hay un servidor", self.pet._mcp_connect("github"))

    def test_desconectar_limpia_tools(self):
        self.pet._mcp_connect("fake")
        out = self.pet._mcp_disconnect("fake")
        self.assertIn("Desconectado", out)
        self.assertNotIn("mcp_fake_echo", self.pet.TOOL_REGISTRY)

    def test_cmd_estado_y_llamada_manual(self):
        self.assertIn("desconectado", self.pet._mcp_cmd(""))
        self.pet._mcp_cmd("conectar fake")
        self.assertIn("conectado, 1 tools", self.pet._mcp_cmd(""))
        out = self.pet._mcp_cmd('llamar fake echo {"text": "manual"}')
        self.assertEqual(out, "ECO: manual")
        self.assertIn("mcp_fake_echo", self.pet._mcp_cmd("tools"))

    def test_cmd_sin_config(self):
        pet = FakePet({})
        self.assertIn("sin servidores configurados", pet._mcp_cmd(""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
