class Datatypes():
    integer = 0
    text = 1

    required = 10
    primary_key = 11
    foreign_key = 12


class Field():
    def __init__(self, appearance: str, *datatype):
        self.appearance = appearance
        self.datatypes = datatype

    def __repr__(self):
        return self.appearance

    def __str__(self):
        return self.appearance

class FieldList():
    def __init__(self, *fields):
        self.index = 0
        self.fields = [Field(*f) for f in fields]
        [self.__setattr__(str(f), f) for f in self.fields]

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


from knife.models.label import Label
from knife.models.ingredient import Ingredient
from knife.models.dish import Dish
from knife.models.requirement import Requirement
from knife.models.tag import Tag
from knife.models.dependency import Dependency

objects = [Dish, Ingredient, Label, Requirement, Tag, Dependency]
