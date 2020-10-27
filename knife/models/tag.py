from knife.models import Datatypes, FieldList

class Tag:
    table_name = 'tags'
    fields = FieldList(('recipe_id', Datatypes.text, Datatypes.primary_key),
                        ('label_id', Datatypes.text, Datatypes.primary_key))
