# -*- coding: UTF-8 -*-
import asyncio
import contextlib
import functools
import inspect
import logging
import typing

import orjson
from psycopg import AsyncConnection, AsyncCursor
from psycopg.types.json import set_json_dumps, set_json_loads
from psycopg_pool import AsyncConnectionPool
from psycopg_pool.abc import AsyncKwargsParam

from atinypgtool.utils import ConfigureFunc, SequencePlaceholder

set_json_loads(orjson.loads)
set_json_dumps(orjson.dumps)

_NAMED_POOL_DICT: dict[str, AsyncConnectionPool] = {}
_POOL_CHECKER_TASK_DICT: dict[str, asyncio.Task[None]] = {}

logger = logging.getLogger(__name__)


async def _check_pool_forever(
    *,
    name: str,
    pool: AsyncConnectionPool,
    interval: int,
) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            await pool.check()
        except Exception as e:
            logger.error(
                'Postgres pool "%s" health check failed',
                name,
                exc_info=e,
            )


def _ensure_pool_checker(
    *,
    name: str,
    pool: AsyncConnectionPool,
    interval: int,
) -> None:
    task = _POOL_CHECKER_TASK_DICT.get(name)
    if task and not task.done():
        return
    _POOL_CHECKER_TASK_DICT[name] = asyncio.create_task(
        _check_pool_forever(name=name, pool=pool, interval=interval),
        name=f'postgres-pool-checker-{name}',
    )


async def _stop_pool_checker(*, name: str) -> None:
    task = _POOL_CHECKER_TASK_DICT.pop(name, None)
    if not task:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def _stop_pool_checkers() -> None:
    for name in tuple(_POOL_CHECKER_TASK_DICT):
        await _stop_pool_checker(name=name)


async def init(
    *,
    name: str,
    dsn: str,
    pool_size: int = 16,
    open_timeout: int = 15,
    health_check_interval: int = 0,
    configure_funcs: typing.Sequence[ConfigureFunc] = SequencePlaceholder,
) -> None:
    if name in _NAMED_POOL_DICT:
        raise SyntaxError(f'Pool "{name}" already exists')
    if pool_size < 1:
        raise SyntaxError('Pool size should be greater than 0')
    if health_check_interval < 0:
        raise SyntaxError('Health check interval should not be less than 0')
    minsize, maxsize = pool_size, pool_size
    if minsize > 4:
        minsize = 4
    kwargs: AsyncKwargsParam = {
        'autocommit': False,
        # 新建连接超过 5 秒未完成时快速失败，避免请求长时间卡在重连上。
        'connect_timeout': 5,
        # 开启 TCP keepalive 探测，用于发现已经被网络或数据库断开的空闲连接。
        'keepalives': 1,
        # TCP 连接空闲 15 秒后发送第一次 keepalive 探测。
        'keepalives_idle': 15,
        # 第一次探测后，如果没有响应，每隔 5 秒继续重试探测。
        'keepalives_interval': 5,
        # 连续 3 次 keepalive 探测无响应后，将连接视为已断开。
        'keepalives_count': 3,
    }

    configure = None
    if configure_funcs:

        async def _configure(conn: AsyncConnection) -> None:
            for func in configure_funcs:
                if inspect.iscoroutinefunction(func):
                    await func(conn)
                else:
                    func(conn)

        configure = _configure

    pool = AsyncConnectionPool(
        conninfo=dsn,
        min_size=minsize,
        max_size=maxsize,
        open=False,
        configure=configure,
        name=name,
        kwargs=kwargs,
        check=AsyncConnectionPool.check_connection,
        num_workers=4,
        timeout=5,
        reconnect_timeout=30,
    )
    await pool.open(wait=True, timeout=open_timeout)
    _NAMED_POOL_DICT[name] = pool
    if health_check_interval > 0:
        _ensure_pool_checker(
            name=name,
            pool=pool,
            interval=health_check_interval,
        )


async def close(*, name: str) -> None:
    if name not in _NAMED_POOL_DICT:
        raise ValueError(f'Pool "{name}" not found')
    pool = _NAMED_POOL_DICT.pop(name)
    await _stop_pool_checker(name=name)
    await pool.close()


async def close_all() -> None:
    await _stop_pool_checkers()
    for pool in _NAMED_POOL_DICT.values():
        await pool.close()
    _NAMED_POOL_DICT.clear()


def with_cursor(*, name: str, transaction: bool) -> typing.Callable:
    def wrapper(func: typing.Callable) -> typing.Callable:
        argspec = inspect.getfullargspec(func)
        if all('cursor' not in x for x in (argspec.args, argspec.kwonlyargs)):
            raise SyntaxError('`cursor` is a required argument')

        @functools.wraps(func)
        async def wrapped(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
            if name not in _NAMED_POOL_DICT:
                raise SyntaxError(f'Pool "{name}" not found')
            if 'cursor' in kwargs and kwargs['cursor']:
                raise SyntaxError('`cursor` is a reserved argument')
            async with _NAMED_POOL_DICT[name].connection() as conn:  # noqa: SIM117
                async with conn.cursor() as cursor:
                    kwargs['cursor'] = cursor
                    if transaction:
                        async with conn.transaction():
                            result = await func(*args, **kwargs)
                    else:
                        result = await func(*args, **kwargs)
            return result

        return wrapped

    return wrapper


@contextlib.asynccontextmanager
async def with_cursor_context(
    *,
    name: str,
    transaction: bool,
) -> typing.AsyncGenerator[AsyncCursor, None]:
    if name not in _NAMED_POOL_DICT:
        raise RuntimeError(f'Pool "{name}" not found')
    async with _NAMED_POOL_DICT[name].connection() as conn:  # noqa: SIM117
        async with conn.cursor() as cursor:
            if transaction:
                async with conn.transaction():
                    yield cursor
            else:
                yield cursor
