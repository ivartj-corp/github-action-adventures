from .merge_queue import (
        get_deplvls,
        CircularDependencyException,
)


def test_get_deplvls_0() -> None:
    deplvls = get_deplvls(tuple[tuple[str, frozenset[str]], ...]())
    assert deplvls == ()


def test_get_deplvls_1() -> None:
    deplvls = get_deplvls((("foo", frozenset()),))
    assert deplvls == ({"foo"},)


def test_get_deplvls_2() -> None:
    deplvls = get_deplvls((("foo", frozenset({"bar", "baz"})),))
    assert deplvls == ({"bar", "baz"}, {"foo"})
        

def test_get_deplvls_3() -> None:
    deplvls = get_deplvls((
        ("foo", frozenset({"bar", "baz"})),
        ("bar", frozenset({"baz", "zoo"})),
    ))
    assert deplvls == (
        {"baz", "zoo"},
        {"bar"},
        {"foo"},
    )


def test_get_deplvls_4() -> None:
    import pytest
    with pytest.raises(CircularDependencyException):
        _ = get_deplvls((
            ("foo", frozenset({"bar", "baz"})),
            ("bar", frozenset({"baz", "foo"})),
        ))
