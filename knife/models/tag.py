from knife.models import Datatypes, Attributes, FieldList


class Tag:
    table_name = 'tags'
    fields = FieldList(('recipe_id', Datatypes.text, Attributes.primary_key),
                       ('label_id', Datatypes.text, Attributes.primary_key))
