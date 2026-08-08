import typing
from collections.abc import Awaitable, Callable, Sequence

from psycopg import AsyncConnection, AsyncCursor
from psycopg.rows import DictRow, TupleRow


class _SequencePlaceholder[T](Sequence[T]):
    @typing.overload
    def __getitem__(self, index: int, /) -> T: ...

    @typing.overload
    def __getitem__(self, index: slice[int | None], /) -> Sequence[T]: ...

    @typing.override
    def __getitem__(self, index: int | slice, /) -> T | Sequence[T]:
        raise SyntaxError('SequencePlaceholder is empty')

    @typing.override
    def __len__(self) -> int:
        return 0

    def __bool__(self) -> bool:
        return False


SequencePlaceholder = _SequencePlaceholder[typing.Never]()


type ConfigureFunc = Callable[
    [AsyncConnection[DictRow | TupleRow]],
    Awaitable[None] | None,
]

class _CursorPlaceholder:
    def __bool__(self) -> bool:
        return False


CursorPlaceholder = typing.cast(
    AsyncCursor[TupleRow],
    typing.cast(object, _CursorPlaceholder()),
)
