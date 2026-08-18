from typing import TextIO
from collections.abc import Iterable
import random
import sys
import os

from fs.base import FS


class GitHubCicdDriver:
    def __init__(
        self,
        fs: FS,
        stdout: TextIO = sys.stdout,
    ) -> None:
        self._fs = fs
        self._stdout = stdout

    @property
    def fs(self) -> FS:
        return self._fs

    def warning(self, message: str) -> None:
        # see https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#setting-a-warning-message
        self._stdout.write(f"::warning::{message}\n")
        self._stdout.flush()

    def error(self, message: str) -> None:
        # see https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#setting-an-error-message
        self._stdout.write(f"::error::{message}\n")
        self._stdout.flush()

    def getenv(self, name: str) -> str | None:
        return os.getenv(name)

    def setenv(self, name: str, value: str) -> None:
        # see https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#setting-an-environment-variable
        os.environ[name] = value
        env_file_path = self.getenv("GITHUB_ENV")
        if env_file_path is None:
            raise Exception("GITHUB_ENV is not set")
        with self.fs.open(path=env_file_path, mode="a", encoding="utf-8") as env_file:
            if "\n" not in value:
                env_file.write(f"{name}={value}\n")
            else:

                def delimiter_generator() -> Iterable[str]:
                    yield "EOF"
                    while True:
                        yield f"EOF{random.randrange(1 << 64)}"

                delimiter = next(
                    delimiter
                    for delimiter in delimiter_generator()
                    if delimiter not in value
                )
                env_file.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
