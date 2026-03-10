import typer
from typing import Annotated
from cryptography.hazmat.primitives.serialization import load_pem_public_key
import shutil
import dataclasses
from dataclasses import dataclass
import subprocess
import json
import shlex
from itertools import chain
from .util.codeowners import CodeOwners


app = typer.Typer()


@dataclass
class Change:
    changed_files: list[str]
    approvers: list[str]


@app.command()
def help():
    app(["--help"])


@app.command()
def diff(
    base: Annotated[
        str,
        typer.Argument(help="base commit"),
    ],
    head: Annotated[
        str,
        typer.Argument(help="head commit"),
    ],
) -> None:
    git_path = shutil.which("git")
    if git_path is None:
        raise Exception("git executable not found in PATH")

    completed_process = subprocess.run(
        [git_path, "diff", "--name-only", "-z", f"{base}...{head}", "--"],
        check=True,
        stdout=subprocess.PIPE,
    )
    paths: list[str] = [
        path.decode("utf-8")
        for path in completed_process.stdout.removesuffix(b"\0").split(b"\0")
    ]

    codeowners = CodeOwners(
        subprocess.run(
            [git_path, "show", f"{base}:CODEOWNERS"],
            check=True,
            stdout=subprocess.PIPE,
        ).stdout.decode("utf-8")
    )
    approvers: list[str] = list(
        chain.from_iterable(codeowners.assignees(path) for path in paths)
    )

    change = Change(
        changed_files=paths,
        approvers=approvers,
    )

    print(
        json.dumps(
            dataclasses.asdict(change),
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
