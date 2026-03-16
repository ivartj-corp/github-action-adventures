import typer
from typing import Annotated
import shutil
import dataclasses
from dataclasses import dataclass
import subprocess
import json
from itertools import chain
from .util.codeowners import CodeOwners
from .util import config_util
import yaml
import re

app = typer.Typer()


@dataclass
class Change:
    changed_files: list[str]
    approvers: list[str]


@app.command()
def help():
    app(["--help"])


@app.command()
def codeowners(
    paths: Annotated[
        list[str],
        typer.Argument(
        ),
    ],
    codeowners_file_path: Annotated[
        str,
        typer.Option(
            help="path to CODEOWNERS file",
        ),
    ] = "CODEOWNERS",
) -> None:
    with open(
            file=codeowners_file_path,
            encoding="utf-8",
    ) as codeowners_file:
        codeowners = CodeOwners(codeowners_file.read())

    owners: set[str] = {
        owner
        for path in paths
        for owner in codeowners(path)
    }
    for owner in sorted(owners):
        print(owner)


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
    approvers: set[str] = set(chain.from_iterable(codeowners(path) for path in paths))

    change = Change(
        changed_files=paths,
        approvers=list(approvers),
    )

    print(
        json.dumps(
            dataclasses.asdict(change),
            indent=2,
        )
    )


@app.command()
def config_diff(
    base_config_path: Annotated[
        str,
        typer.Argument(help="base config"),
    ],
    head_config_path: Annotated[
        str,
        typer.Argument(help="head config"),
    ],
    map: Annotated[
        list[str] | None,
        typer.Option(
            "-m", "--map",
            help=(
                "Map configuration setting paths to file paths with syntax SRC_PATH:DESTINATION_PATH:BASEPREFIX."
                " Path prefixes are matched against SRC_PATH, which gets replaced by DESTINATION_PATH."
                " The base filename gets prefixed with BASEPREFIX."
            )
        )
    ] = None,
    null_terminate: Annotated[
        bool,
        typer.Option(
            "-z", "--null-terminate",
            help="terminate paths with null bytes instead of newlines",
        ),
    ] = False,
) -> None:
    if map is None:
        map = []
    mappings: list[tuple[str, str,str]] = []
    for m in map:
        if len([c for c in m if c == ":"]) != 2:
            raise Exception("the --map/-m option expects a SRC_PATH:DESTINATION_PATH:BASEPREFIX syntax")
        src, dest, prefix = m.split(":")
        mappings.append((src, dest, prefix))

    with (
        open(
            file=base_config_path,
            encoding="utf-8",
        ) as base_file,
        open(
            file=head_config_path,
            encoding="utf-8",
        ) as head_file,
    ):
        base_config: object = yaml.safe_load(base_file)  # pyright: ignore[reportAny]
        head_config: object = yaml.safe_load(head_file)  # pyright: ignore[reportAny]

    changed_key_paths: list[str] = []
    for key_path in config_util.changed_key_paths(base_config, head_config):
        changed_key_paths.append("/".join(str(part) for part in key_path))
    changed_key_paths.sort()

    terminator = '\0' if null_terminate else '\n'
    for key_path in changed_key_paths:
        for src, dest, prefix in reversed(mappings):
            if key_path.startswith(src):
                key_path = dest + key_path.removeprefix(src)
                if (basenamematch := re.search(r"(^|\/)([^\/]+)$", key_path)) is not None:
                    key_path = key_path[:basenamematch.start(2)] + prefix + basenamematch.group(2)
                break

        if terminator in key_path:
            raise Exception(f'terminator exists in path {key_path}')
        print(key_path, end=terminator)

if __name__ == "__main__":
    app()
