from knife.models import Datatypes, FieldList

class Requirement:
    table_name = 'requirements'
    fields = FieldList(('dish_id', Datatypes.text, Datatypes.primary_key),
                        ('ingredient_id', Datatypes.text, Datatypes.primary_key),
                        ('quantity', Datatypes.text))
