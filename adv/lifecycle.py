from collections import defaultdict
import types
import typing
import asyncio
import collections.abc

from .util import msgraph


class PropertyFact(typing.NamedTuple):
    subject_ref: str
    property: str
    value: str


class RelationFact(typing.NamedTuple):
    subject_ref: str
    relation_type: typing.Literal["owner_of", "member_of"]
    object_ref: str


Fact = RelationFact | PropertyFact


class PartialSetSpec(typing.TypedDict):
    include: list[str] | None
    exclude: list[str] | None


SetSpec: typing.TypeAlias = list[str] | PartialSetSpec


class Group(typing.TypedDict):
    display_name: str
    unique_name: str | None
    owners: SetSpec
    members: SetSpec


class Application(typing.TypedDict):
    display_name: str
    unique_name: str | None
    groups: SetSpec | None
    owners: SetSpec | None


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
        
        








