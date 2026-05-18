"""Claudy subagent runner. Spawned as isolated subprocess via /delegate."""
import json
import os
import sys
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
    out_dir = os.path.join(os.path.expanduser("~"), ".claudy", "subagents")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{sid}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"id": sid, "task": task, "status": "running"}, f)
    result = call_claudy(task)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"id": sid, "task": task, "status": "done", "result": result}, f, ensure_ascii=False, indent=2)
    print(result[:500])


if __name__ == "__main__":
    main()
