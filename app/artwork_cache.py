import hashlib
import logging
import os
import tempfile
from pathlib import Path

from app.settings import CONFIG_DIR

logger = logging.getLogger(__name__)
ARTWORK_CACHE_DIR = Path(CONFIG_DIR) / "artwork"


class ArtworkCache:
    def path_for(self, server: str, cover_id: str, size: int) -> Path:
        cache_key = f"{server.rstrip('/')}|{cover_id}|{size}"
        filename = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()
        return ARTWORK_CACHE_DIR / f"{filename}.img"

    def load(self, server: str, cover_id: str, size: int) -> bytes | None:
        path = self.path_for(server, cover_id, size)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError:
            logger.warning("Could not read cached artwork: %s", path, exc_info=True)
            return None

    def remove(self, server: str, cover_id: str, size: int) -> None:
        path = self.path_for(server, cover_id, size)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not remove invalid cached artwork: %s", path, exc_info=True)

    def store(self, server: str, cover_id: str, size: int, data: bytes) -> None:
        if not data:
            return

        path = self.path_for(server, cover_id, size)
        temporary_path = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=path.parent, suffix=".tmp", delete=False
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(data)
            os.replace(temporary_path, path)
        except OSError:
            logger.warning("Could not cache artwork: %s", path, exc_info=True)
            if temporary_path:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning(
                        "Could not remove temporary artwork cache file: %s",
                        temporary_path,
                        exc_info=True,
                    )
