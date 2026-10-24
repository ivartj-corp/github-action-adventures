#!/usr/bin/env python3

from dataclasses import dataclass
import argparse
from pathlib import Path
import sys
import json
import typing


class CircularDependencyException(Exception):
    pass


def get_deplvls(
        modules: tuple[tuple[str, set[str]], ...],
) -> tuple[set[str], ...]:
    @dataclass
    class Module:
        name: str
        dependents: set[str]
        dependencies: set[str]
        deplvl: int = 0
    name2module: dict[str, Module] = {}
    for module_name, dependencies in modules:
        if module_name not in name2module:
            name2module[module_name] = Module(
                name=module_name,
                dependencies=set(dependencies),
                dependents=set(),
            )
        else:
            name2module[module_name].dependencies.update(dependencies)
        for dependency in dependencies:
            if dependency not in name2module:
                name2module[dependency] = Module(
                    name=dependency,
                    dependencies=set(),
                    dependents={module_name},
                )
            else:
                name2module[dependency].dependents.add(module_name)
    deepest_deplvl = 0
    stack: list[tuple[str,...]] = list(
        (name,)
        for name in name2module.keys()
    )
    while len(stack) != 0:
        dependency_chain = stack.pop()
        module = name2module[dependency_chain[-1]]
        raised_deplvl = False
        for dependency in module.dependencies:
            deplvl = name2module[dependency].deplvl
            if module.deplvl <= deplvl:
                module.deplvl = deplvl + 1
                raised_deplvl = True
                if module.deplvl > deepest_deplvl:
                    deepest_deplvl = module.deplvl
        if raised_deplvl:
            for dependent in module.dependents:
                new_chain = (*dependency_chain, dependent)
                if dependent in dependency_chain:
                    raise CircularDependencyException("circular dependency: " + " -> ".join(new_chain))
                stack.append(new_chain)
                    
    deplvls: tuple[set[str], ...] = (
        tuple(
            set(
                module.name
                for module in name2module.values()
                if module.deplvl == deplvl
            )
            for deplvl in range(0, deepest_deplvl+1)
        )
        if len(modules) != 0
        else tuple[set[str], ...]()
    )
    return deplvls


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    deplvls_parser = subparsers.add_parser("deplvls")
    deplvls_parser.set_defaults(subcommand="deplvls")
    _ = deplvls_parser.add_argument("--max-deplvls", type=int, default=5)
    _ = deplvls_parser.add_argument("input_file", default="-", nargs="?")

    parentpaths_parser = subparsers.add_parser("parentpaths")
    parentpaths_parser.set_defaults(subcommand="parentpaths")
    _ = parentpaths_parser.add_argument("input_file", default="-", nargs="?")

    args = parser.parse_args(sys.argv[1:])
    subcommand = typing.cast(str, args.subcommand)
    match subcommand:

        case "deplvls":
            max_deplvls: int = typing.cast(int, args.max_deplvls)
            input_file_path = typing.cast(str, args.input_file)
            input = sys.stdin if input_file_path == "-" else open(input_file_path, encoding="utf-8")
            with input:
                module_json = typing.cast(
                    dict[str, list[str]],
                    json.load(input),
                )
            modules = tuple(
                (key, set(value))
                for key, value in module_json.items()
            )
            deplvls = get_deplvls(modules)
            print(json.dumps([list(deplvl) for deplvl in deplvls]))
            if len(deplvls) > max_deplvls:
                raise Exception(f"number of deplvls exceed maximum of {max_deplvls}")

        case "parentpaths":
            input_file_path = typing.cast(str, args.input_file)
            input = sys.stdin if input_file_path == "-" else open(input_file_path, encoding="utf-8")
            printed_paths: set[Path] = set()
            def print_path(path: Path) -> None:
                if path not in printed_paths:
                    print(path)
                    printed_paths.add(path)
            with input:
                for line in input:
                    line = line.removesuffix("\n")
                    for parent in Path(line).parents:
                        print_path(parent)

        case _:
            raise Exception("unimplemented command '%s'" % subcommand)


if __name__ == "__main__":
    main()
