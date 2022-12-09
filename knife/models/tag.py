from knife.models import Datatypes, Attributes, FieldList, Recipe, Label


class Tag:
    table_name = 'tags'
    fields = FieldList(
        ('recipe_id', Recipe.fields.id_type, Attributes.primary_key),
        ('label_id', Label.fields.id_type, Attributes.primary_key),
    )
