import json
import logging
import os
import tempfile

from app.settings import CONFIG_DIR

logger = logging.getLogger(__name__)
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")


def load_app_state() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as state_file:
            state = json.load(state_file)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not load saved app state.", exc_info=True)
        return {}
    return state if isinstance(state, dict) else {}


def save_app_state(state: dict) -> None:
    temporary_path = None
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=CONFIG_DIR,
            suffix=".tmp",
            delete=False,
        ) as state_file:
            temporary_path = state_file.name
            json.dump(state, state_file)
        os.replace(temporary_path, STATE_FILE)
    except (OSError, TypeError):
        logger.warning("Could not save app state.", exc_info=True)
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
            except OSError:
                logger.warning(
                    "Could not remove temporary app state file: %s",
                    temporary_path,
                    exc_info=True,
                )
