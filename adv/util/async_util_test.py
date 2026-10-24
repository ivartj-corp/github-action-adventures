import asyncio

from . import async_util


def test_closable_queue() -> None:
    items = "foo", "bar", "baz"
    async def producer(queue: async_util.ClosableQueue[str]) -> None:
        for item in items:
            print(f"put {item}")
            await queue.put(item)
        await queue.close()

    async def consumer(queue: async_util.ClosableQueue[str]) -> None:
        item_index = 0
        async for item in queue:
            print(f"itr {item}")
            assert items[item_index] == item
            item_index += 1
        
    async def main() -> None:
        async with async_util.ClosableQueue[str]() as queue:
            producer_task = asyncio.create_task(producer(queue))
            consumer_task = asyncio.create_task(consumer(queue))
            _ = await asyncio.gather(producer_task, consumer_task)
    asyncio.run(main())
