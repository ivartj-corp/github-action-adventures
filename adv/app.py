import typer
from typing import Annotated
from cryptography.hazmat.primitives.serialization import load_pem_public_key
import shutil
import dataclasses
from dataclasses import dataclass
import subprocess
import json


app = typer.Typer()


@dataclass
class Change:
    changed_files: list[str]


@app.command()
def help():
    app(["--help"])




@app.command()
def diff(
        base: Annotated[
            str,
            typer.Argument(
                help="base commit"
            ),
        ],
        head: Annotated[
            str,
            typer.Argument(
                help="head commit"
            ),
        ],
) -> None:
    git_path = shutil.which("git")
    if git_path is None:
        raise Exception("git executable not found in PATH")
    
    completed_process = subprocess.run(
        [
            git_path,
            "diff",
            "--name-only",
            "-z",
            f"{base}...{head}",
            "--"
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    paths: list[str] = [
        path.decode("utf-8")
        for path in completed_process.stdout.removesuffix(b"\0").split(b'\0')
    ]
    change = Change(
        changed_files=paths,
    )

    print(
        json.dumps(
            dataclasses.asdict(change),
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
