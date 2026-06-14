"""Claudy subagent runner. Spawned as isolated subprocess via /delegate."""
import json
import os
import sys
import time
import urllib.request

GATEWAY = "http://127.0.0.1:8720/api"


def call_claudy(task):
    try:
        req = urllib.request.Request(
            GATEWAY,
            data=json.dumps({"message": task}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read()).get("response", "")
    except Exception as e:
        return f"ERROR: {e}"


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: subagent_runner.py <id> <task>"}))
        sys.exit(1)
    sid = sys.argv[1]
    task = " ".join(sys.argv[2:])
    # B4 — linaje: el padre que nos lanzó propaga su id por env (o "root" si lo
    # lanzó el proceso principal). root_task es la tarea de la raíz del árbol.
    parent = os.environ.get("CLAUDY_PARENT_ID") or "root"
    root_task = os.environ.get("CLAUDY_ROOT_TASK") or task
    started = time.time()
    out_dir = os.path.join(os.path.expanduser("~"), ".claudy", "subagents")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{sid}.json")
    meta = {"id": sid, "task": task, "parent": parent,
            "root_task": root_task, "started": started}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dict(meta, status="running"), f)
    result = call_claudy(task)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dict(meta, status="done", result=result, finished=time.time()),
                  f, ensure_ascii=False, indent=2)
    print(result[:500])


if __name__ == "__main__":
    main()
