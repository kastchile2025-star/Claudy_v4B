"""Memory providers for Claudy.

Default: SQLite (built into pet.py).
External: Mem0 (vectorial, requires `pip install mem0ai` + API key).

Config in ~/.claudy/config.json:
  "memory": {
    "provider": "mem0",
    "mem0_api_key": "...",
    "user_id": "felipe"
  }
"""
import os


class SqliteProvider:
    """Pass-through to native SQLite memory."""
    def __init__(self, pet):
        self.pet = pet

    def save(self, role, text):
        return self.pet._save_memory_sqlite(role, text)

    def search(self, query, top_k=10):
        return self.pet._search_memory_sqlite(query, top_k)


class Mem0Provider:
    def __init__(self, config):
        try:
            from mem0 import MemoryClient
            self.client = MemoryClient(api_key=config.get("mem0_api_key", "") or os.environ.get("MEM0_API_KEY", ""))
        except Exception as e:
            raise RuntimeError(f"Mem0 no instalado: {e}. pip install mem0ai")
        self.user_id = config.get("user_id", "default")

    def save(self, role, text):
        try:
            self.client.add(
                messages=[{"role": role.lower(), "content": text}],
                user_id=self.user_id,
            )
            return True
        except Exception:
            return False

    def search(self, query, top_k=10):
        try:
            results = self.client.search(query=query, user_id=self.user_id, limit=top_k)
            return [
                {"role": "Usuario", "text": r.get("memory", "")}
                for r in (results or [])
            ]
        except Exception:
            return []


def get_provider(config, pet):
    """Return active memory provider based on config."""
    mem_cfg = (config or {}).get("memory", {})
    name = (mem_cfg.get("provider") or "sqlite").lower()
    if name == "mem0":
        try:
            return Mem0Provider(mem_cfg)
        except Exception as e:
            print(f"[memory] fallback a SQLite: {e}")
    return SqliteProvider(pet)
