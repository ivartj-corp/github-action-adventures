from collections.abc import Generator
from itertools import chain


def flatten(
        config: object,
        prefix: tuple[str | int, ...] = (),
) -> Generator[tuple[tuple[str | int, ...], object]]:
    if isinstance(config, dict):
        for key, value in config.items():
            if isinstance(key, str):
                sub_prefix = prefix + (key,)
                yield from flatten(value, sub_prefix)
            else:
                raise Exception(f"non-string key {key} in configuration")
    elif isinstance(config, list):
        for index, value in enumerate(config):
            sub_prefix = prefix + (index,)
            yield from flatten(value, sub_prefix)
    else:
        yield prefix, config


def changed_key_paths(base_config: object, head_config: object) -> Generator[tuple[str | int, ...]]:
    flat_base = dict(flatten(base_config))
    flat_head = dict(flatten(head_config))

    for key in set(chain(flat_base.keys(), flat_head.keys())):
        base_value = flat_base.get(key)
        head_value = flat_head.get(key)
        match base_value, head_value:
            case None, None:
                pass
            case None, _:
                yield key
            case _, None:
                yield key
            case base_value, head_value:
                if base_value != head_value:
                    yield key
