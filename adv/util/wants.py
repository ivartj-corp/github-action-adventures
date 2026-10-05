from typing import Literal, TypeAlias, Annotated
import builtins

from pydantic import BaseModel, Field


Want: TypeAlias = Annotated[
    "ObjectWant | ArrayWant | ValueWant | ObjectFieldWant | ArraySetWant | ArrayIncludeWant | ArrayExcludeWant",
    Field(discriminator="type"),
]


class ObjectWant(BaseModel):
    """A want for an object which also satisfies wants in the `wants` list."""
    type: Literal["object"] = "object"
    wants: list[Want]

    def apply(self, current: builtins.object | None) -> builtins.object | None:
        if isinstance(current, dict):
            updated = current  # pyright: ignore[reportUnknownVariableType]
        else:
            updated = {}

        for want in self.wants:
            updated = want.apply(updated)

        return updated

    def satisfied_by(self, value: builtins.object | None) -> bool:
        for desire in self.wants:
            if not desire.satisfied_by(value):
                return False
        return True


class ArrayWant(BaseModel):
    """A want for an array which also satisfies wants in the `wants` list."""
    type: Literal["array"] = "array"
    wants: list[Want]

    def apply(self, current: builtins.object | None) -> builtins.object | None:
        if isinstance(current, list):
            updated = current
        else:
            updated = []

        for desire in self.wants:
            updated = desire.apply(updated)

        return updated

    def satisfied_by(self, value: builtins.object | None) -> bool:
        for desire in self.wants:
            if not desire.satisfied_by(value):
                return False
        return True            


class ObjectFieldWant(BaseModel):
    """A want for an object with the given field, with a field value that satisified the `value` want."""
    type: Literal["object_field"] = "object_field"
    field: str
    value: Want

    def apply(self, current: builtins.object | None) -> builtins.object | None:
        if isinstance(current, dict):
            updated = current.copy()  # pyright: ignore[reportUnknownVariableType]
            current_field_value: builtins.object | None = updated.get(self.field)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        else:
            updated = {}
            current_field_value = None
        updated[self.field] = self.value.apply(current_field_value)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        return updated

    def satisfied_by(self, value: builtins.object | None) -> bool:
        if not isinstance(value, dict):
            return False
        field = value.get(self.field)
        return self.value.satisfied_by(field)


class ValueWant(BaseModel):
    """A want for a value which is equal to `value`."""
    type: Literal["exact"] = "exact"
    value: builtins.object | None

    def apply(self, current: builtins.object | None) -> builtins.object | None:
        return self.value

    def satisfied_by(self, value: builtins.object | None) -> bool:
        return value == self.value


class ArrayIncludeWant(BaseModel):
    """A want for an array which contains an element identified by the `key` want and which satisifes the `value` want."""
    type: Literal["array_include"] = "array_include"
    key: Want
    value: Want | None

    def apply(self, current: object | None) -> object | None:
        if isinstance(current, list):
            updated = current.copy()
        else:
            updated = []

        match_indices: list[int] = [
            index
            for index in range(0, len(updated))
            if self.key.satisfied_by(updated[index])
        ]

        if len(match_indices) == 0:
            value = self.key.apply(None)
            if self.value is not None:
                value = self.value.apply(value)
            updated.append(value)
        elif self.value is not None:
            for index in match_indices:
                updated[index] = self.value.apply(updated[index])
                        
        return updated

    def satisfied_by(self, value: object | None) -> bool:
        if not isinstance(value, list):
            return False
        return any(
            self.key.satisfied_by(element)
            for element in value
            if self.value is None or self.value.satisfied_by(element)
        )

    
class ArrayExcludeWant(BaseModel):
    """A want for an array which does not contains any element which satisfies the `key` want."""
    type: Literal["array_exclude"] = "array_exclude"
    key: Want

    def apply(self, current: object | None) -> object | None:
        if isinstance(current, list):
            return [
                element
                for element in current
                if not self.key.satisfied_by(element)
            ]
        else:
            return []

    def satisfied_by(self, value: object | None) -> bool:
        if isinstance(value, list):
            return not any(
                self.key.satisfied_by(element)
                for element in value
            )
        else:
            return False
        

class ArraySetWant(BaseModel):
    """A want for an array which contains unique values satisfying the given wants in any order."""
    type: Literal["array_set"] = "array_set"
    values: list[Want]

    def apply(self, current: object | None) -> object | None:
        if isinstance(current, list):
            old_list = current
            new_list = []
            unsatisfied_value_want_indices: list[int] = list(range(0, len(self.values)))
            for list_value in old_list:
                for value_want_index in unsatisfied_value_want_indices:
                    value_want = self.values[value_want_index]
                    if value_want.satisfied_by(list_value):
                        new_list.append(list_value)
                        unsatisfied_value_want_indices.remove(value_want_index)
                        break
            for value_want_index in unsatisfied_value_want_indices:
                value_want = self.values[value_want_index]
                new_list.append(value_want.apply(None))
            return new_list
        else:
            return [
                value.apply(None)
                for value in self.values
            ]

    def satisfied_by(self, value: object | None) -> bool:
        if isinstance(value, list):
            if len(self.values) != len(value):
                return False
            satisfying_values_indices: set[int] = set()
            for value_want in self.values:
                satisfying_value_index = set(
                    index
                    for index, list_value in enumerate(value)
                    if value_want.satisfied_by(list_value)
                )
                if len(satisfying_value_index) != 1:
                    return False
                if len(satisfying_values_indices & satisfying_value_index) != 0:
                    return False
            return True
        else:
            return False


def object(*args: Want) -> Want:
    return ObjectWant(
        wants=list(args),
    )


def array(*args: Want) -> Want:
    return ArrayWant(
        wants=list(args),
    )


def value(value: builtins.object | None) -> Want:
    return ValueWant(
        value=value,
    )


def object_field(name: str, value: Want) -> Want:
    return ObjectFieldWant(
        field=name,
        value=value,
    )


def array_set(*args: Want) -> Want:
    return ArraySetWant(
        values=list(args),
    )


def array_include(key: Want, value: Want | None = None) -> Want:
    return ArrayIncludeWant(
        key=key,
        value=value,
    )


def array_exclude(key: Want) -> Want:
    return ArrayExcludeWant(
        key=key,
    )

