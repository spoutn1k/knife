import time
from knife import helpers
from dataclasses import dataclass
from typing import Any, Optional, Mapping


class Datatypes():
    INTEGER = 0
    TEXT = 1
    BOOLEAN = 2

    REQUIRED = 10
    PRIMARY_KEY = 11
    FOREIGN_KEY = 12


@dataclass(frozen=True)
class Field:
    name: str
    datatype: frozenset[Datatypes]
    default: Any = None

    def __init__(self, name, datatype, default=None):
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "datatype", frozenset(datatype))
        object.__setattr__(self, "default", default)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.name == other.name and self.datatype == other.datatype


class FieldList():

    def __init__(self, *fields):
        self.index = 0
        for f in fields:
            self.__setattr__(f.name, f)
            self.__setattr__(f.name + '_type', f.datatype)
            self.__setattr__(f.name + '_default', f.default)
        self.fields = fields

    def __iter__(self):
        return self

    def __next__(self):
        try:
            result = self.fields[self.index].name

        except IndexError:
            self.index = 0
            raise StopIteration

        self.index += 1
        return result


def get_field(field: Field, data: Mapping) -> Optional[Any]:
    if not field in data:
        if field.default is not None:
            return field.default
        return None
    elif field in data:
        raw_data = data[field]
    elif field.name in data:
        raw_data = data[field]

    if Datatypes.INTEGER in field.datatype:
        return int(raw_data)
    elif Datatypes.BOOLEAN in field.datatype:
        return raw_data in ['true', True, 'True']
    elif Datatypes.TEXT in field.datatype:
        return str(raw_data)

    return raw_data


class KnifeModel:

    def __init__(self, *args, **kwargs):
        if len(args) == 1 and isinstance(args[0], dict):
            kwargs = args[0]
        for field in self.fields.fields:
            if field.name == 'simple_name':
                continue
            value = get_field(field, kwargs)
            if value is not None:
                self.__setattr__(field.name, value)

        if 'id' in set(self.fields) and 'id' not in kwargs:
            generated_id = helpers.hash256("{}{}".format(
                self.name, time.time()))
            self.__setattr__('id', generated_id)

    @property
    def simple_name(self):
        return helpers.simplify(self.name)

    @property
    def params(self):
        components = map(
            lambda f: (f, getattr(self, f.name, None)),
            self.fields.fields,
        )

        return dict(components)

    @property
    def serializable(self):
        components = map(
            lambda f: (f.name, getattr(self, f.name, None)),
            self.fields.fields,
        )

        return dict(components)
