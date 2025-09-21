from typing import Protocol, Literal, Optional
from fs.memoryfs import MemoryFS
from fs.base import FS
import traceback
import logging
import fs


class CicdDriverProtocol(Protocol):
    @property
    def fs(self) -> FS: ...

    def setenv(self, name: str, value: str) -> None: ...

    def getenv(self, name: str) -> str | None: ...

    def warning(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...
