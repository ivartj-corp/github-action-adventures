from typing import TextIO
import os
import sys

from fs.base import FS


class DevOpsCicdDriver:
    def __init__(
        self,
        fs: FS,
        stdout: TextIO = sys.stdout,
    ) -> None:
        self._stdout = stdout
        self._fs = fs

    @property
    def fs(self) -> FS:
        return self._fs

    def warning(self, message: str) -> None:
        # see https://learn.microsoft.com/en-us/azure/devops/pipelines/scripts/logging-commands?view=azure-devops&tabs=bash#logissue-log-an-error-or-warning
        self._stdout.write(f"##vso[task.logissue type=warning]{message}\n")
        self._stdout.flush()

    def error(self, message: str) -> None:
        # see https://learn.microsoft.com/en-us/azure/devops/pipelines/scripts/logging-commands?view=azure-devops&tabs=bash#logissue-log-an-error-or-warning
        self._stdout.write(f"##vso[task.logissue type=error]{message}\n")
        self._stdout.flush()

    def setenv(self, name: str, value: str) -> None:
        # see https://learn.microsoft.com/en-us/azure/devops/pipelines/process/set-variables-scripts?view=azure-devops&tabs=bash
        os.environ[name.upper().replace(".", "_")] = value  # match self.getenv
        self._stdout.write(f"##vso[task.setvariable variable={name};]")
        escaped_value = (
            value.replace("%", "%AZP25").replace("\n", "%0A").replace("\r", "%0D")
        )
        self._stdout.write(f"{escaped_value}\n")
        self._stdout.flush()

    def getenv(self, name: str) -> str | None:
        # see https://learn.microsoft.com/en-us/azure/devops/pipelines/process/variables?view=azure-devops&tabs=yaml%2Cbatch#environment-variables
        name = name.upper().replace(".", "_")
        return os.getenv(name)
