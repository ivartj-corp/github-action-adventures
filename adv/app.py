import typer
from typing import Annotated
from cryptography.hazmat.primitives.serialization import load_pem_public_key
import shutil
import shlex
import subprocess


app = typer.Typer()


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
    
    subprocess.run(
        [
            git_path,
            "diff",
            "--names-only",
            f"{base}...{head}",
            "--"
        ],
        check=True,
    )


if __name__ == "__main__":
    app()
