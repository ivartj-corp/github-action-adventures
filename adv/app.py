import typer
from typing import Annotated
import typing
import pathlib
import shutil
import dataclasses
from dataclasses import dataclass
import subprocess
import json
from .util.codeowners import CodeOwners
from .util import config_util
import yaml
import re
import pydantic
import fnmatch


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
        list[str] | None,
        typer.Argument(
        ),
    ] = None,
    codeowners_file_path: Annotated[
        str,
        typer.Option(
            help="path to CODEOWNERS file",
        ),
    ] = "CODEOWNERS",
) -> None:
    if paths is None:
        paths = []
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
    approvers: set[str] = set(
        codeowner
        for path in paths
        for codeowner in codeowners(path)
    )

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


@app.command()
def tk_build_check(
        build_dir: typing.Annotated[
            pathlib.Path | None,
            typer.Option(
                help="Directory containing resources built with Cognite Toolkit",
            )
        ] = None,
        module_authorization_file: typing.Annotated[
            pathlib.Path | None,
            typer.Option(
                help="File specifying which modules are allowed to deploy which types of resources",
            )
        ] = None,
) -> None:
    if build_dir is None:
        build_dir = pathlib.Path("./build")
    if module_authorization_file is None:
        module_authorization_file = pathlib.Path("./module_authorization.yaml")

    build_lineage_object: object = yaml.safe_load((build_dir / "lineage.yaml").read_text())  # pyright: ignore[reportAny]
    class BuildLineage(pydantic.BaseModel):
        moduleLineage: list["ModuleLineage"]
    class ModuleLineage(pydantic.BaseModel):
        moduleId: str
        resourceLineage: list["ResourceLineage"]
    class ResourceType(pydantic.BaseModel):
        resource_folder: str
        kind: str
    class ResourceLineage(pydantic.BaseModel):
        sourceFile: str
        builtFile: str
        type: ResourceType
        identifier: dict[str, str]
    build_lineage = BuildLineage.model_validate(build_lineage_object)

    module_authorization_object: object = yaml.safe_load(module_authorization_file.read_text())  # pyright: ignore[reportAny]
    class ModuleAuthorization(pydantic.BaseModel):
        type: dict[typing.Literal["resource_folder", "kind"], str]
        identifier: dict[str, str]
        wildcard: bool = False
    prefix2authorizations = pydantic.TypeAdapter(dict[str, list[ModuleAuthorization]]).validate_python(module_authorization_object)

    for module_lineage in build_lineage.moduleLineage:
        module_id = module_lineage.moduleId
        implicit_authorizations: list[ModuleAuthorization] = []
        for resource_lineage in module_lineage.resourceLineage:
            type = resource_lineage.type
            match type.resource_folder, type.kind:
                case "raw", "Database":
                    for db_name_key in "dbName", "name":
                        implicit_authorizations.append(
                            ModuleAuthorization(
                                type={"resource_folder": "raw"},
                                identifier={
                                    db_name_key: resource_lineage.identifier["name"]
                                },
                                wildcard=True
                            )
                        )
                case "data_modeling", "Space":
                    implicit_authorizations.append(
                        ModuleAuthorization(
                            type={"resource_folder": "data_modeling"},
                            identifier={
                                "space": resource_lineage.identifier["space"]
                            },
                            wildcard=True
                        )
                    )
                case _, _:
                    pass
        authorizations: list[ModuleAuthorization] = [
            authorization
            for prefix, authorizations in prefix2authorizations.items()
            if module_id.startswith(prefix)
            for authorization in authorizations
        ] + implicit_authorizations
        for resource_lineage in module_lineage.resourceLineage:
            authorized_resource = False
            for authorization in authorizations:
                if not authorization.wildcard and frozenset(authorization.type.keys()) != frozenset(resource_lineage.type.model_dump().keys()):
                    continue
                for type_key, auth_type_value in authorization.type.items():
                    resource_type_value: str = getattr(resource_lineage.type, type_key)  # pyright: ignore[reportAny]
                    if authorization.wildcard and not fnmatch.fnmatchcase(resource_type_value, auth_type_value):
                        continue
                    elif resource_type_value != auth_type_value:
                        continue
                if not authorization.wildcard and frozenset(authorization.identifier.keys()) != frozenset(resource_lineage.identifier.keys()):
                    continue
                for id_key, auth_id_value in authorization.identifier.items():
                    resource_id_value = resource_lineage.identifier.get(id_key)
                    if resource_id_value is None:
                        continue
                    elif authorization.wildcard and not fnmatch.fnmatchcase(resource_id_value, auth_id_value):
                        continue
                    elif resource_id_value != auth_id_value:
                        continue
                authorized_resource = True
                break
            if not authorized_resource:
                raise Exception(f"module {module_id} is not authorized to deploy {resource_lineage}")

if __name__ == "__main__":
    app()
