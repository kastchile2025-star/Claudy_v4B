import os
import json
import time
import threading
import uuid
import datetime

class TaskScheduler:
    def __init__(self, pet_instance=None):
        self.pet = pet_instance
        self.running = False
        self.thread = None
        self.tasks_file = os.path.join(os.path.expanduser("~"), ".claudy", "tasks.json")
        self.logs_dir = os.path.join(os.path.expanduser("~"), ".claudy", "task_logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Seed default tasks if file doesn't exist
        if not os.path.exists(self.tasks_file):
            self.save_tasks([])

    def load_tasks(self):
        try:
            if os.path.exists(self.tasks_file):
                with open(self.tasks_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[Scheduler] Error loading tasks: {e}")
        return []

    def save_tasks(self, tasks):
        try:
            os.makedirs(os.path.dirname(self.tasks_file), exist_ok=True)
            with open(self.tasks_file, "w", encoding="utf-8") as f:
                json.dump(tasks, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Scheduler] Error saving tasks: {e}")

    def add_task(self, name, prompt, interval_minutes):
        tasks = self.load_tasks()
        new_task = {
            "id": f"task_{uuid.uuid4().hex[:8]}",
            "name": name,
            "prompt": prompt,
            "interval_minutes": int(interval_minutes),
            "last_run": 0.0,
            "enabled": True
        }
        tasks.append(new_task)
        self.save_tasks(tasks)
        return new_task

    def delete_task(self, task_id):
        tasks = self.load_tasks()
        filtered = [t for t in tasks if t["id"] != task_id]
        self.save_tasks(filtered)
        return len(tasks) != len(filtered)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="claudy-scheduler")
        self.thread.start()
        print("[Scheduler] Background task scheduler started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
        print("[Scheduler] Background task scheduler stopped.")

    def _scheduler_loop(self):
        while self.running:
            # Re-load tasks list dynamically in case user edited it via CLI/UI
            tasks = self.load_tasks()
            now = time.time()
            updated = False
            
            for task in tasks:
                if not task.get("enabled", True):
                    continue
                
                last_run = task.get("last_run", 0.0)
                interval_secs = task.get("interval_minutes", 60) * 60
                
                if now - last_run >= interval_secs:
                    # Mark run time immediately to prevent multiple triggers
                    task["last_run"] = now
                    updated = True
                    # Run in a separate thread so it doesn't block the scheduler loop
                    threading.Thread(
                        target=self._run_task_worker,
                        args=(task,),
                        daemon=True,
                        name=f"task-worker-{task['id']}"
                    ).start()
            
            if updated:
                self.save_tasks(tasks)
                
            time.sleep(10)

    def _run_task_worker(self, task):
        task_id = task["id"]
        name = task["name"]
        prompt = task["prompt"]
        print(f"[Scheduler] Running task '{name}' ({task_id})...")
        
        result = ""
        try:
            if self.pet:
                # Call send_quick_message (blocking LLM call)
                # Ensure we skip skills to avoid UI popups or recursive triggers
                result = self.pet.send_quick_message(prompt, _skip_skill_action=True)
            else:
                result = "Error: Instancia de Claudy no disponible para ejecutar la tarea."
        except Exception as e:
            result = f"Error al ejecutar la tarea: {e}"
            print(f"[Scheduler] Exception running task '{name}': {e}")
            
        # Save output log
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(self.logs_dir, f"{task_id}_{ts}.txt")
        try:
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"TASK ID: {task_id}\n")
                f.write(f"NAME: {name}\n")
                f.write(f"TIMESTAMP: {datetime.datetime.now().isoformat()}\n")
                f.write(f"PROMPT: {prompt}\n")
                f.write("="*40 + "\n\n")
                f.write(result)
        except Exception as e:
            print(f"[Scheduler] Error writing log file: {e}")
            
        # Trigger native Windows notification
        if self.pet:
            notification_text = result[:120] + "..." if len(result) > 120 else result
            self.pet.after(0, lambda: self.pet._show_notification(
                f"Tarea ejecutada: {name}", 
                notification_text
            ))
            # Insert a system message into the active chat view if open
            chat_v = getattr(self.pet, "_chat_view", None)
            if chat_v:
                # Append link to log file or simple message
                self.pet.after(0, lambda: chat_v.add_system(f"✓ Tarea '{name}' completada en segundo plano."))
