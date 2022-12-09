from knife.models import Datatypes, Attributes, FieldList, Recipe


class Dependency:
    table_name = 'dependencies'
    fields = FieldList(
        ('required_by', Recipe.fields.id_type, Attributes.primary_key),
        ('requisite', Recipe.fields.id_type, Attributes.primary_key),
    )
