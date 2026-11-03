import typer
from typing import Annotated
import typing
import pathlib
import shutil
import dataclasses
from dataclasses import dataclass
import subprocess
import json
from collections import defaultdict
from .util.codeowners import CodeOwners
from .util import config_util
import yaml
import re
import pydantic
import fnmatch
import logging
import itertools


app = typer.Typer()
logger = logging.getLogger(pathlib.Path(__file__).name)


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
        build_dir_str: typing.Annotated[
            str,
            typer.Option(
                "--build-dir",
                help="Directory containing resources built with Cognite Toolkit",
            )
        ] = "build/",
        modules_config_dir_str: typing.Annotated[
            str,
            typer.Option(
                "--module-authorization-dir",
                help="File specifying which modules are allowed to deploy which types of resources",
            )
        ] = "modules-config/",
) -> None:
    build_dir = pathlib.Path(build_dir_str)
    modules_config_dir = pathlib.Path(modules_config_dir_str)

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


    @dataclass
    class ResourceWildcard:
        type: dict[typing.Literal["resource_folder", "kind"], str | None]
        identifier: dict[str, str] = dataclasses.field(default_factory=dict)
        properties: dict[str, str] = dataclasses.field(default_factory=dict)
    @dataclass
    class AuthzGrant:
        source_path: pathlib.Path
        resource_wildcard: ResourceWildcard
    modules = [module_lineage.moduleId for module_lineage in build_lineage.moduleLineage]
    module2grants: dict[str, list[AuthzGrant]] = {module: [] for module in modules}

    all_resource_types: frozenset[tuple[str, str]] = frozenset(
        (resource_lineage.type.resource_folder, resource_lineage.type.kind)
        for module_lineage in build_lineage.moduleLineage
        for resource_lineage in module_lineage.resourceLineage
    )
    space_scoped_types = frozenset(
        (resource_folder, kind)
        for resource_folder, kind in all_resource_types
        if resource_folder == "data_modeling"
    ) - {("data_modeling", "Space")}
    dataset_scoped_types = frozenset({
        ("transformations", "Transformation"),
        ("extraction_pipelines", "ExtractionPipeline"),
        ("workflows", "Workflow"),
    })
    workflow_scoped_types = frozenset(
        (resource_folder, kind)
        for resource_folder, kind in all_resource_types
        if resource_folder == "workflows"
    ) - {("workflows", "Workflow")}

    unscoped_resource_types = all_resource_types \
        - space_scoped_types \
        - dataset_scoped_types \
        - workflow_scoped_types

    auth_resource_types = frozenset(
        (resource_folder, kind)
        for resource_folder, kind in all_resource_types
        if resource_folder == "auth"
    )

    # Grant all modules the ability to deploy any unscoped resource that do not control authorization.
    # We will check elsewhere that the resource does not already exist in a different module.
    for resource_folder, kind in unscoped_resource_types - auth_resource_types:
        for grants in module2grants.values():
            grants.append(
                AuthzGrant(
                    resource_wildcard=ResourceWildcard(
                        type={
                            "resource_folder": resource_folder,
                            "kind": kind,
                        },
                        identifier={},
                    ),
                    source_path=pathlib.Path(__file__),
                )
            )

    # Add grants for resources scoped to scopes in the module
    for module_lineage in build_lineage.moduleLineage:
        module = module_lineage.moduleId
        for resource_lineage in module_lineage.resourceLineage:
            resource_folder = resource_lineage.type.resource_folder
            kind = resource_lineage.type.kind
            match resource_folder, kind:
                case "data_modeling", "Space":
                    module2grants[module].extend(
                        AuthzGrant(
                            source_path=pathlib.Path(resource_lineage.sourceFile),
                            resource_wildcard=ResourceWildcard(
                                type={
                                    "resource_folder": resource_folder,
                                    "kind": kind,
                                },
                                identifier={
                                    "space": resource_lineage.identifier["space"],
                                },
                            )
                        )
                        for resource_folder, kind in space_scoped_types
                    )
                case "data_sets", "DataSet":
                    module2grants[module].extend(
                        AuthzGrant(
                            source_path=pathlib.Path(resource_lineage.sourceFile),
                            resource_wildcard=ResourceWildcard(
                                type={
                                    "resource_folder": resource_folder,
                                    "kind": kind,
                                },
                                identifier={},
                                properties={
                                    "dataSetExternalId": resource_lineage.identifier["externalId"],
                                },
                            ),
                        )
                        for resource_folder, kind in dataset_scoped_types
                    )
                case "workflows", "Workflow":
                    module2grants[module].extend(
                        AuthzGrant(
                            source_path=pathlib.Path(resource_lineage.sourceFile),
                            resource_wildcard=ResourceWildcard(
                                type={
                                    "resource_folder": resource_folder,
                                    "kind": kind,
                                },
                                identifier={},
                                properties={
                                    "workflowExternalId": resource_lineage.identifier["externalId"],
                                },
                            ),
                        )
                        for resource_folder, kind in workflow_scoped_types
                    )
                case _:
                    pass

    # Add explicit grants
    class AuthzFileEntry(pydantic.BaseModel):
        resources: list[ResourceWildcard]
        modules: list[str]
    for authz_file_path in modules_config_dir.glob("**/authz.yaml"):
        authz_file_object = yaml.safe_load(authz_file_path.read_text())  # pyright: ignore[reportAny]
        authz_file_entries = pydantic.TypeAdapter(list[AuthzFileEntry]).validate_python(authz_file_object)
        granting_module = str(pathlib.PosixPath("modules") / authz_file_path.parent.relative_to(modules_config_dir))
        granting_module_grants = list(
            itertools.chain.from_iterable(
                grants
                for module_id, grants in module2grants.items()
                if module_id == granting_module or module_id.startswith(granting_module + "/")
            )
        )
        for entry in authz_file_entries:
            for resource_wildcard in entry.resources:
                authorized_grant = False
                if granting_module == "modules":
                    logger.info(f"{authz_file_path} grant for {resource_wildcard} authorized by {__file__}")
                    authorized_grant = True
                for grant in granting_module_grants:
                    if any(
                            grant_type_value != resource_wildcard.type.get(type_key)
                            for type_key, grant_type_value in grant.resource_wildcard.type.items()
                    ):
                        continue
                    if any(
                            grant_id_value != resource_wildcard.identifier.get(id_key)
                            for id_key, grant_id_value in grant.resource_wildcard.identifier.items()
                    ):
                        continue
                    if any(
                            grant_property_value != resource_wildcard.properties.get(property_key)
                            for property_key, grant_property_value in grant.resource_wildcard.properties
                    ):
                        continue
                    logger.info(f"{authz_file_path} grant for {resource_wildcard} authorized by {grant.source_path}")
                    authorized_grant = True
                if not authorized_grant:
                    logger.info(f"{authz_file_path} grant for {resource_wildcard} not authorized")
            recipient_modules = [
                module
                for module in modules
                if any(module.startswith(module_prefix) for module_prefix in entry.modules)
            ]
            for recipient_module in recipient_modules:
                module2grants[recipient_module].extend(
                    AuthzGrant(
                        source_path=authz_file_path,
                        resource_wildcard=resource_wildcard
                    )
                    for resource_wildcard in entry.resources
                )

    for module_lineage in build_lineage.moduleLineage:
        top_level_module = "/".join(module_lineage.moduleId.split("/")[:2])
        grants = list(
            itertools.chain.from_iterable(
                grants
                for module_id, grants in module2grants.items()
                if module_id == top_level_module or module_id.startswith(top_level_module + "/")
            )
        )
        for resource_lineage in module_lineage.resourceLineage:
            authorized_resource = False
            resource_type = {
                "resource_folder": resource_lineage.type.resource_folder,
                "kind": resource_lineage.type.kind,
            }
            resource_id = resource_lineage.identifier
            for grant in grants:
                if any(
                        grant_type_value != resource_type.get(type_key)
                        for type_key, grant_type_value in grant.resource_wildcard.type.items()
                ):
                    continue
                if any(
                        resource_id.get(id_key) != grant_id_value
                        for id_key, grant_id_value in grant.resource_wildcard.identifier.items()
                ):
                    continue
                if len(properties := grant.resource_wildcard.properties) != 0:
                    resource_manifest: object | None = yaml.safe_load((pathlib.Path(build_dir) / resource_lineage.builtFile).read_text())  # pyright: ignore[reportAny]
                    if not isinstance(resource_manifest, dict):
                        continue
                    if any(
                        resource_manifest.get(property) != grant_property_value  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
                        for property, grant_property_value in properties.items()
                    ):
                        continue
                logger.info(f"{resource_lineage.sourceFile} authorized by {grant.source_path}")
                authorized_resource = True
            if not authorized_resource:
                logger.error(f"{resource_lineage.sourceFile} not authorized")


@app.callback()
def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
    )


if __name__ == "__main__":
    app()
