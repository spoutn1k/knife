class Datatypes():
    integer = 0
    text = 1


class Attributes():
    required = 10
    primary_key = 11
    foreign_key = 12


class Field():

    def __init__(self, appearance: str, datatype: int, *attributes):
        self.appearance = appearance
        self.datatype = datatype
        self.attributes = attributes

    def __repr__(self):
        return self.appearance

    def __str__(self):
        return self.appearance


class FieldList():

    def __init__(self, *fields):
        self.index = 0
        self.fields = [Field(*f) for f in fields]
        [self.__setattr__(str(f), str(f)) for f in self.fields]
        [self.__setattr__(str(f) + '_type', f.datatype) for f in self.fields]

    def __iter__(self):
        return self

    def __next__(self):
        try:
            result = str(self.fields[self.index])

        except IndexError:
            self.index = 0
            raise StopIteration

        self.index += 1
        return result


from knife.models.user import User
from knife.models.label import Label
from knife.models.ingredient import Ingredient
from knife.models.recipe import Recipe
from knife.models.requirement import Requirement
from knife.models.tag import Tag
from knife.models.dependency import Dependency

OBJECTS = [Recipe, Ingredient, Label, Requirement, Tag, Dependency]
