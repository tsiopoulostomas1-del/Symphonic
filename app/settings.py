import os
import json

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".symphonic")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def load_settings() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"server": "", "username": "", "password": ""}

def save_settings(server: str, username: str, password: str):
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    with open(CONFIG_FILE, "w") as f:
        json.dump({"server": server, "username": username, "password": password}, f)