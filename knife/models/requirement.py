from knife.models import Datatypes, Attributes, FieldList, Recipe, Ingredient


class Requirement:
    table_name = 'requirements'
    fields = FieldList(
        ('recipe_id', Recipe.fields.id_type, Attributes.primary_key),
        ('ingredient_id', Ingredient.fields.id_type, Attributes.primary_key),
        ('quantity', Datatypes.text))
