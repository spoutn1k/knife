from knife.models import Datatypes, FieldList

class Tag:
    table_name = 'tags'
    fields = FieldList(('dish_id', Datatypes.text, Datatypes.primary_key),
                        ('label_id', Datatypes.text, Datatypes.primary_key))
