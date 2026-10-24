from collections import defaultdict
import types
import typing
import asyncio
import collections.abc

from .util import msgraph


class PartialRefSetSpec(typing.TypedDict):
    include: list[str] | None
    exclude: list[str] | None


RefSetSpec: typing.TypeAlias = list[str] | PartialRefSetSpec


class GroupSpec(typing.TypedDict):
    type: typing.Literal["group"]
    id: str | None
    display_name: str
    unique_name: str | None
    owners: RefSetSpec | None
    members: RefSetSpec | None


class ApplicationSpec(typing.TypedDict):
    type: typing.Literal["application"]
    id: str | None
    display_name: str
    unique_name: str | None
    groups: RefSetSpec | None
    owners: RefSetSpec | None


ResourceSpec = GroupSpec | ApplicationSpec


def resource_spec_query_needs(spec: ResourceSpec) -> collections.abc.Generator[tuple[str, str]]:
    match spec["type"]:
        case "application":
            if (id := spec.get("id")) is not None:
                id_escaped = id.replace("'", "''")
                yield "/applications", f"id eq '{id_escaped}'"
            if (unique_name := spec.get("unique_name")) is not None:
                unique_name_escaped = unique_name.replace("'", "''")
                yield "/applications", f"uniqueName eq '{unique_name_escaped}'"
            if (ref_set_spec := spec.get("owners")) is not None:
                yield from ref_set_query_needs(ref_set_spec)
        case "group":
            if (id := spec.get("id")) is not None:
                id_escaped = id.replace("'", "''")
                yield "/groups", f"id eq '{id_escaped}'"
            if (unique_name := spec.get("unique_name")) is not None:
                unique_name_escaped = unique_name.replace("'", "''")
                yield "/applications", f"uniqueName eq '{unique_name_escaped}'"


def ref_set_query_needs(spec: RefSetSpec) -> collections.abc.Generator[tuple[str, str]]:
    match spec:
        case list():
            pass
        case dict():
            pass


def ref_query(ref: str) -> tuple[str, str]:
    

class QueryAggregator[T]:
    _query_callback: typing.Callable[[str], collections.abc.AsyncIterable[T]]
    _filter2queues: defaultdict[str, list[asyncio.Queue[T]]]
    _listeners: list[asyncio.Queue[T]]

    def __init__(self, query_callback: typing.Callable[[str], collections.abc.AsyncIterable[T]]) -> None:
        self._query_callback = query_callback
        self._filter2queues = defaultdict(list)
        self._listeners = []

    async def add_query(
            self,
            query_filter: str,
    ) -> collections.abc.AsyncGenerator[T]:
        queue: asyncio.Queue[T] = asyncio.Queue()
        self._filter2queues[query_filter].append(queue)
        
        async for element in queue:
            yield element

    async def run_queries(self) -> None:
        
        pass
        
        








