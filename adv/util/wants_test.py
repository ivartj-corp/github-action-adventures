from . import wants


def test_basic() -> None:
    current = {
        "foo": 123,
        "bar": [1,2,3],
        "baz": [
            { "id": 1, "x": 123, "y": 321 },
            { "id": 2, "x": 456, "y": 654 },
            { "id": 3, "x": 789, "y": 987 },
        ],
        "capabilities": [
            {
                "actions": ["READ", "WRITE"],
                "scopes": [ "A", "B" ],
            }
        ]
    }

    want = wants.object(
        wants.object_field("foo", wants.value(321)),
        wants.object_field("bar", wants.array(
            wants.array_include(wants.value(3)),
            wants.array_include(wants.value(4)),
        )),
        wants.object_field("baz", wants.array(
            wants.array_exclude(
                key=wants.object_field("id", wants.value(1)),
            ),
            wants.array_include(
                key=wants.object_field("id", wants.value(2)),
                value=wants.object_field("x", wants.value(-123)),
            ),
            wants.array_include(
                key=wants.object_field("id", wants.value(4)),
                value=wants.object(
                    wants.object_field("x", wants.value(121)),
                    wants.object_field("y", wants.value(212)),
                ),
            ),
        )),
        wants.object_field("capabilities", wants.array(
            wants.array_include(
                key=wants.object_field("actions", wants.array_set(
                    wants.value("READ"),
                    wants.value("WRITE"),
                )),
                value=wants.object_field("scopes", wants.array_include(
                    wants.value("C")
                )),
            ),
            wants.array_include(
                key=wants.object_field("actions", wants.array_set(
                    wants.value("READ"),
                )),
                value=wants.object_field("scopes", wants.array_include(
                    wants.value("D")
                )),
            ),
        )),
    )

    updated = want.apply(current)

    assert updated == {
        "foo": 321,
        "bar": [1,2,3,4],
        "baz": [
            { "id": 2, "x": -123, "y": 654 },
            { "id": 3, "x": 789, "y": 987 },
            { "id": 4, "x": 121, "y": 212 },
        ],
        "capabilities": [
            {
                "actions": ["READ", "WRITE"],
                "scopes": [ "A", "B", "C" ],
            },
            {
                "actions": ["READ"],
                "scopes": [ "D" ],
            }
        ]
    }
    assert want.satisfied_by(updated)
