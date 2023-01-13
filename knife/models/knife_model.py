import time
from knife import helpers
from dataclasses import dataclass
from typing import Any


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


class KnifeModel:

    @property
    def id(self):
        if not self._id:
            self._id = helpers.hash256("{}{}".format(self.name, time.time()))
        return self._id

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
