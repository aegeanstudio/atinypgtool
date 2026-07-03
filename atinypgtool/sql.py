# -*- coding: utf-8 -*-
import dataclasses
import inspect
import typing

from psycopg.sql import SQL

from atinypgtool.utils import SequencePlaceholder


class SQLHelper:
    def __init__(self, base_model_cls: type | None = None) -> None:
        if base_model_cls is not None:
            try:
                assert isinstance(base_model_cls, type)
                assert dataclasses.is_dataclass(base_model_cls)
            except AssertionError as e:
                raise SyntaxError(
                    f'Base model "{base_model_cls}" '
                    f'should be a dataclass or None',
                ) from e
        self._base_model_cls = base_model_cls

    def _gen_fields(self, *, dataclass: type) -> tuple[list[str], list[str]]:
        default_fields = []
        if self._base_model_cls is not None and issubclass(
            dataclass,
            self._base_model_cls,  # noqa: type: ignore
        ):
            default_fields = [
                i.strip('_')
                for i in inspect.get_annotations(self._base_model_cls)
            ]
        custom_fields = [
            i.strip('_') for i in inspect.get_annotations(dataclass)
        ]
        return default_fields, custom_fields

    def gen_select_base(
        self,
        *,
        dataclass: type,
        table_name: str,
    ) -> str:
        default_fields, custom_fields = self._gen_fields(dataclass=dataclass)
        return (
            f'SELECT {", ".join(default_fields + custom_fields)} '
            f'FROM {table_name}'
        )

    def gen_get(self, *, dataclass: type, table_name: str) -> SQL:
        default_fields, custom_fields = self._gen_fields(dataclass=dataclass)
        return self.make_sql(
            sql_str=(
                f'SELECT {", ".join(default_fields + custom_fields)} '
                f'FROM {table_name} WHERE id=%s'
            ),
        )

    def gen_insert(
        self,
        *,
        dataclass: type,
        table_name: str,
        limited_fields: typing.Sequence[str] = SequencePlaceholder,
    ) -> SQL:
        _, custom_fields = self._gen_fields(dataclass=dataclass)
        if limited_fields and (
            not set(limited_fields).issubset(set(custom_fields))
        ):
            unexcepted = set(limited_fields) - set(custom_fields)
            raise SyntaxError(f'Field names not allowed: {unexcepted}')
        fields = limited_fields or custom_fields
        return self.make_sql(
            sql_str=(
                f'INSERT INTO {table_name} ({", ".join(fields)}) '
                f'VALUES ({", ".join(["%s"] * len(fields))})'
            ),
        )

    def gen_insert_returning(
        self,
        *,
        dataclass: type,
        table_name: str,
        limited_fields: typing.Sequence[str] = SequencePlaceholder,
    ) -> SQL:
        default_fields, custom_fields = self._gen_fields(dataclass=dataclass)
        if limited_fields and (
            not set(limited_fields).issubset(set(custom_fields))
        ):
            unexcepted = set(limited_fields) - set(custom_fields)
            raise SyntaxError(f'Field names not allowed: {unexcepted}')
        fields = limited_fields or custom_fields
        return self.make_sql(
            sql_str=(
                f'INSERT INTO {table_name} ({", ".join(fields)}) '
                f'VALUES ({", ".join(["%s"] * len(fields))}) '
                f'RETURNING {", ".join(default_fields + custom_fields)}'
            ),
        )

    @staticmethod
    def make_sql(*, sql_str: str) -> SQL:
        return SQL(obj=sql_str.strip())  # type: ignore
