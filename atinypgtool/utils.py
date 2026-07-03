# -*- coding: utf-8 -*-
import dataclasses
import typing

from psycopg import AsyncConnection, AsyncCursor
from psycopg.pq import PGconn


class _SequencePlaceholder[T](typing.Sequence):
    @typing.overload
    def __getitem__(self, index: int, /) -> T: ...

    @typing.overload
    def __getitem__(self, index: slice, /) -> typing.Sequence[T]: ...

    def __getitem__(self, _, /):
        raise SyntaxError('SequencePlaceholder is empty')

    def __len__(self) -> int:
        return 0

    def __bool__(self) -> bool:
        return False


SequencePlaceholder = _SequencePlaceholder[typing.Any]()


type ConfigureFunc = typing.Callable[
    [AsyncConnection],
    typing.Awaitable | None,
]


@typing.runtime_checkable
class DataclassInstance(typing.Protocol):
    __dataclass_fields__: typing.ClassVar[
        dict[str, dataclasses.Field[typing.Any]]
    ]


class _PGConnPlaceholder(PGconn):
    pass


class _CursorPlaceholder(AsyncCursor):
    def __init__(self) -> None:
        super().__init__(
            connection=AsyncConnection(pgconn=_PGConnPlaceholder()),
        )

    def __bool__(self) -> bool:
        return False


CursorPlaceholder = _CursorPlaceholder()
