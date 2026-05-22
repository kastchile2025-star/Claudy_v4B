import os
import sys
import json
import shutil

local_config = "config.json"
backup_config = "config_backup_safe.json"

def clean_secrets():
    if not os.path.exists(local_config):
        print("No config.json found in current directory.")
        return
    
    # Create backup
    shutil.copy2(local_config, backup_config)
    print("✓ Copia de seguridad temporal segura config_backup_safe.json creada.")
    
    with open(local_config, "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)
        
    # Strip secrets
    if "opencode" in cfg:
        cfg["opencode"]["apiKey"] = "YOUR_OPENCODE_API_KEY_HERE"
    if "telegram" in cfg:
        cfg["telegram"]["botToken"] = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    if "providers" in cfg:
        if "deepseek" in cfg["providers"]:
            cfg["providers"]["deepseek"]["key"] = "YOUR_DEEPSEEK_API_KEY_HERE"
            cfg["providers"]["deepseek"]["keys"] = ["YOUR_DEEPSEEK_API_KEY_HERE"]
        if "openai" in cfg["providers"]:
            cfg["providers"]["openai"]["key"] = "YOUR_OPENAI_API_KEY_HERE"
            cfg["providers"]["openai"]["keys"] = []
            
    with open(local_config, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print("✓ Credenciales de la API y tokens privadas removidos temporalmente para evitar la detección de secretos de GitHub.")

def restore_secrets():
    if os.path.exists(backup_config):
        shutil.move(backup_config, local_config)
        print("✓ Copia de seguridad restaurada con éxito. Tus llaves locales están seguras y activas.")
    else:
        print("No backup file found to restore.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python push_handler.py [prepare|restore]")
        sys.exit(1)
        
    action = sys.argv[1].lower()
    if action == "prepare":
        clean_secrets()
    elif action == "restore":
        restore_secrets()
