from typing import Protocol, Literal, Optional
from fs.memoryfs import MemoryFS
from fs.base import FS
import traceback
import logging
import fs
from .types import CicdContextProtocol


class DummyCicdContext:
    _warnings: list[str]
    _errors: list[str]

    def __init__(self) -> None:
        self._env = {}
        self._fs = MemoryFS()
        self._warnings = []
        self._errors = []

    @property
    def fs(self) -> FS:
        return self._fs

    def setenv(self, name: str, value: str) -> None:
        self._env[name] = value

    def getenv(self, name: str) -> str | None:
        return self._env.get(name)

    def warning(self, message: str) -> None:
        self._warnings.append(message)

    def error(self, message: str) -> None:
        self._errors.append(message)


def test_cicd() -> None:
    ctx: CicdContextProtocol = DummyCicdContext()
    ctx.fs.makedirs("/foo/bar")
    with ctx.fs.open("/foo/bar/baz", mode="w", encoding="utf-8") as file:
        file.write("foo\nbar\nbaz")
    file_list = ctx.fs.listdir("/foo/bar")
    assert "baz" in file_list
