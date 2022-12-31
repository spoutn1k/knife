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


from knife.models.label import Label
from knife.models.ingredient import Ingredient
from knife.models.recipe import Recipe
from knife.models.requirement import Requirement
from knife.models.tag import Tag
from knife.models.dependency import Dependency

OBJECTS = [Recipe, Ingredient, Label, Requirement, Tag, Dependency]
