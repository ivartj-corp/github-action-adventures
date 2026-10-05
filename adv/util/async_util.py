import asyncio
import collections.abc
import typing
import types
import contextlib


class ClosableQueue[T](
        collections.abc.AsyncGenerator[T],
        contextlib.AbstractAsyncContextManager["ClosableQueue"],
):
    _closed: bool
    _current_item: asyncio.Future[T] | None
    _can_put: asyncio.Condition
    _can_send: asyncio.Condition

    def __init__(self) -> None:
        self._closed = False
        self._current_item = None
        lock = asyncio.Lock()
        self._can_put = asyncio.Condition(lock)
        self._can_send = asyncio.Condition(lock)

    async def put(self, item: T) -> None:
        _ = await self._can_put.acquire()
        try:
            if self._current_item is None:
                self._current_item = asyncio.get_event_loop().create_future()
            while self._current_item.done():
                if self._closed:
                    raise RuntimeError("attempt to add to closed queue")
                _ = await self._can_put.wait()
            self._current_item.set_result(item)
            self._can_send.notify()
        finally:
            self._can_put.release()

    @typing.override
    async def asend(self, value: None) -> T:
        _ = await self._can_send.acquire()
        try:
            if self._current_item is None:
                self._current_item = asyncio.get_event_loop().create_future()
            while not self._current_item.done():
                if self._closed:
                    raise StopAsyncIteration()
                _ = await self._can_send.wait()
            item = self._current_item.result()
            self._current_item = asyncio.get_event_loop().create_future()
            self._can_put.notify()
            return item
        finally:
            self._can_send.release()

    @typing.override
    async def aclose(self) -> None:
        await self.close()
        await collections.abc.AsyncGenerator.aclose(self)  # pyright: ignore[reportUnknownMemberType]

    @typing.override
    async def athrow(
        self,
        typ: type[BaseException] | BaseException,
        val: BaseException | object = None,
        tb: types.TracebackType | None = None,
        /,
    ) -> T:
        if self._current_item is not None and isinstance(val, BaseException):
            self._current_item.set_exception(val)
        return await super().athrow(
            typ,
            val,
            tb,
        )

    @types.coroutine
    def close(self) -> collections.abc.Generator[None]:
        self._closed = True
        yield None

    @typing.override
    async def __aenter__(self) -> typing.Self:
        return self

    @typing.override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        await self.close()
        
