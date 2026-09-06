#!/usr/bin/env python3

from dataclasses import dataclass
import argparse
from pathlib import Path
import sys
import json
import typing
from typing import TextIO


class CircularDependencyException(Exception):
    pass


def dependency_layers(
        modules: tuple[tuple[str, set[str]], ...],
) -> tuple[set[str], ...]:
    @dataclass
    class Module:
        name: str
        dependents: set[str]
        dependencies: set[str]
        layer: int = 0
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
    deepest_layer = 0
    stack: list[tuple[str,...]] = list(
        (name,)
        for name in name2module.keys()
    )
    while len(stack) != 0:
        dependency_chain = stack.pop()
        module = name2module[dependency_chain[-1]]
        raised_layer = False
        for dependency in module.dependencies:
            dependency_layer = name2module[dependency].layer
            if module.layer <= dependency_layer:
                module.layer = dependency_layer + 1
                raised_layer = True
                if module.layer > deepest_layer:
                    deepest_layer = module.layer
        if raised_layer:
            for dependent in module.dependents:
                new_chain = (*dependency_chain, dependent)
                if dependent in dependency_chain:
                    raise CircularDependencyException("circular dependency: " + " -> ".join(new_chain))
                stack.append(new_chain)
                    
    layers: tuple[set[str], ...] = (
        tuple(
            set(
                module.name
                for module in name2module.values()
                if module.layer == layer
            )
            for layer in range(0, deepest_layer+1)
        )
        if len(modules) != 0
        else tuple[set[str], ...]()
    )
    return layers


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    layers_parser = subparsers.add_parser("layers")
    layers_parser.set_defaults(subcommand="layers")
    layers_parser.add_argument("--max-layers", type=int, default=5)
    layers_parser.add_argument("input_file", default="-", nargs="?")

    parentpaths_parser = subparsers.add_parser("parentpaths")
    parentpaths_parser.set_defaults(subcommand="parentpaths")
    parentpaths_parser.add_argument("input_file", default="-", nargs="?")

    args = parser.parse_args(sys.argv[1:])
    match args.subcommand:

        case "layers":
            max_layers: int = args.max_layers
            input_file_path: str = args.input_file
            input: TextIO = sys.stdin if input_file_path == "-" else open(input_file_path, encoding="utf-8")
            with input:
                module_json = typing.cast(
                    dict[str, list[str]],
                    json.load(input),
                )
            modules = tuple(
                (key, set(value))
                for key, value in module_json.items()
            )
            layers = dependency_layers(modules)
            print(json.dumps([list(layer) for layer in layers]))
            if len(layers) > max_layers:
                raise Exception(f"number of layers exceed maximum of {max_layers}")

        case "parentpaths":
            input_file_path: str = args.input_file
            input: TextIO = sys.stdin if input_file_path == "-" else open(input_file_path, encoding="utf-8")
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
            raise Exception("unimplemented command '%s'" % args.subcommand)


if __name__ == "__main__":
    main()
