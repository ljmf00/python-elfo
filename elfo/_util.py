# SPDX-License-Identifier: EUPL-1.2

from __future__ import annotations

from typing import Any, Dict, Sequence, Tuple, Type, Union


class _Printable():
    """Generates a nice repr showing the object attributes with support for nested objects.

    Might break / look bad if non _Printable attributes have multiple lines in their repr.
    """

    def _pad(self, level: int) -> str:
        return '  ' * level

    def _repr(self, level: int) -> str:
        def value_repr(value: Any) -> str:
            # custom printers
            if isinstance(value, list):
                value = _PrintableSequence(value)
            # print
            if isinstance(value, _Printable):
                return value._repr(level + 1)
            elif isinstance(value, bytes) and len(value) > 32:
                return f'<bytes: size={len(value)}>'
            elif isinstance(value, int) and not isinstance(value, _EnumItem):
                hex_repr = f'{value:x}'
                hex_repr = ('0' * (len(hex_repr) % 2)) + hex_repr
                return f'0x{hex_repr}'
            return repr(value)

        return '{}(\n{}{})'.format(self._name, ''.join(
            '{}{}={},\n'.format(self._pad(level + 1), key, value_repr(value))
            for key, value in self._values.items()
        ), self._pad(level))

    @property
    def _name(self) -> str:
        return self.__class__.__name__

    @property
    def _values(self) -> Dict[Any, Any]:
        return {
            key: value
            for key, value in vars(self).items()
            if not key.startswith('_')
        }

    def __repr__(self) -> str:
        return self._repr(0)


class _PrintableSequence(_Printable):
    def __init__(self, sequence: Sequence[Any]) -> None:
        self.sequence = sequence

    @property
    def _name(self) -> str:
        return ''

    @property
    def _values(self) -> Dict[int, Any]:
        return dict(enumerate(self.sequence))


class _EnumItem(int):
    """Custom int that tracks the enum name."""

    name: str

    def __new__(cls, value: int, name: str) -> _EnumItem:
        obj = super().__new__(cls, value)
        obj.name = name
        return obj

    def __repr__(self) -> str:
        return f'<{self.name}: {int(self)}>'


class _EnumFlagItem(_EnumItem):
    """Like _EnumItem but holds flags."""

    def __repr__(self) -> str:
        return f'<{self.name}: {bin(self)}>'

    def __eq__(self, other: Any) -> bool:
        return bool(self & other)

    def __ne__(self, other: Any) -> bool:
        return not self == other


class _FlagMatch(int, _Printable):
    """Custom int tack tracks flags it matches."""

    flags: Sequence[_EnumFlagItem]

    def __new__(cls, value: int, flags: Sequence[_EnumFlagItem]) -> _FlagMatch:
        obj = super().__new__(cls, value)
        obj.flags = flags
        return obj

    @property
    def _values(self) -> Dict[str, Any]:
        return {
            flag.name: flag == self
            for flag in self.flags
        }


class _EnumMeta(type):
    def __new__(
        mcs,
        name: str,
        bases: Tuple[Any],
        dict_: Dict[str, Any],
        item_cls: Type[_EnumItem] = _EnumItem,
    ) -> _EnumMeta:
        new_dict = {
            key: item_cls(value, f'{name}.{key}') if isinstance(value, int) else value
            for key, value in dict_.items()
        }
        new_dict.update({'_item_cls': item_cls})
        return super().__new__(mcs, name, bases, new_dict)

    @property
    def value_dict(self) -> Dict[int, _EnumItem]:
        return {
            int(value): value
            for value in vars(self).values()
            if isinstance(value, _EnumItem)
        }


class _Enum(metaclass=_EnumMeta):
    _item_cls: Type[_EnumItem]

    @classmethod
    def from_value(cls, value: int) -> Union[_EnumItem, _FlagMatch]:
        if cls._item_cls is _EnumFlagItem:
            return _FlagMatch(value, [
                value for value in vars(cls).values()
                if isinstance(value, _EnumFlagItem)
            ])

        for item in vars(cls).values():
            if item == value:
                assert isinstance(item, _EnumItem)
                return item
        raise ValueError(f'Item not found for 0x{value:x} in {cls.__name__}')

    @classmethod
    def from_value_fallback(cls, value: int) -> int:
        """Like from_value, but falls back to value passed."""
        try:
            return cls.from_value(value)
        except ValueError:
            return value
