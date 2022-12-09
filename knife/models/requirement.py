from knife.models import Datatypes, Attributes, FieldList


class Requirement:
    table_name = 'requirements'
    fields = FieldList(
        ('recipe_id', Datatypes.text, Attributes.primary_key),
        ('ingredient_id', Datatypes.text, Attributes.primary_key),
        ('quantity', Datatypes.text))
