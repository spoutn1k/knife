import time
from knife import helpers
from dataclasses import dataclass
from typing import Any


class Datatypes():
    integer = 0
    text = 1

    required = 10
    primary_key = 11
    foreign_key = 12


@dataclass
class Field:
    name: str
    datatype: list[Datatypes]
    default: Any = None


class FieldList():

    def __init__(self, *fields):
        self.index = 0
        for f in fields:
            self.__setattr__(f.name, f.name)
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
        components = map(lambda f: (f, getattr(self, f, None)), self.fields)

        return dict(components)

    @property
    def serializable(self):
        return self.params
