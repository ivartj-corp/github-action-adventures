from .merge_queue import (
        dependency_layers,
        CircularDependencyException,
)


def test_dependency_layers_0() -> None:
    layers = dependency_layers(tuple[tuple[str, frozenset[str]], ...]())
    assert layers == ()


def test_dependency_layers_1() -> None:
    layers = dependency_layers((("foo", frozenset()),))
    assert layers == ({"foo"},)


def test_dependency_layers_2() -> None:
    layers = dependency_layers((("foo", frozenset({"bar", "baz"})),))
    assert layers == ({"bar", "baz"}, {"foo"})
        

def test_dependency_layers_3() -> None:
    layers = dependency_layers((
        ("foo", frozenset({"bar", "baz"})),
        ("bar", frozenset({"baz", "zoo"})),
    ))
    assert layers == (
        {"baz", "zoo"},
        {"bar"},
        {"foo"},
    )


def test_dependency_layers_4() -> None:
    import pytest
    with pytest.raises(CircularDependencyException):
        _ = dependency_layers((
            ("foo", frozenset({"bar", "baz"})),
            ("bar", frozenset({"baz", "foo"})),
        ))
