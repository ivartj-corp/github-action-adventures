import fs
from fs.base import FS
import traceback
import logging
import os


class LocalCicdDriver:
    def __init__(self, fs: FS) -> None:
        self._fs = fs

    @property
    def fs(self) -> FS:
        return self._fs

    def setenv(self, name: str, value: str) -> None:
        os.environ[name] = value

    def getenv(self, name: str) -> str | None:
        return os.getenv(name)

    def warning(self, message: str) -> None:
        frame = list(traceback.extract_stack(limit=2))[0]
        logging_name = (
            f"{fs.path.basename(frame.filename.removesuffix('.py'))}.{frame.name}"
        )
        logger = logging.getLogger(name=logging_name)
        logger.warning(message)

    def error(self, message: str) -> None:
        frame = list(traceback.extract_stack(limit=2))[0]
        logging_name = (
            f"{fs.path.basename(frame.filename.removesuffix('.py'))}.{frame.name}"
        )
        logger = logging.getLogger(name=logging_name)
        logger.error(message)
