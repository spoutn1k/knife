from dataclasses import dataclass
from knife.models.label import Label
from knife.models.ingredient import Ingredient
from knife.models.recipe import Recipe
from knife.models.requirement import Requirement
from knife.models.tag import Tag
from knife.models.dependency import Dependency

OBJECTS = [Recipe, Ingredient, Label, Requirement, Tag, Dependency]


@dataclass
class Classifications:
    dairy: bool = False
    meat: bool = False
    gluten: bool = False
    animal_product: bool = False

    def __add__(self, other):
        return Classifications(
            self.dairy | other.dairy,
            self.meat | other.meat,
            self.gluten | other.gluten,
            self.animal_product | other.animal_product,
        )

    @property
    def serializable(self):
        return {
            "dairy": self.dairy,
            "meat": self.meat,
            "gluten": self.gluten,
            "animal_product": self.animal_product,
        }
