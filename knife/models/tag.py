from knife.models import Datatypes, FieldList, Field


class Tag:
    table_name = 'tags'
    fields = FieldList(
        Field(name='recipe_id',
              datatype=[Datatypes.text, Datatypes.primary_key]),
        Field(name='label_id',
              datatype=[Datatypes.text, Datatypes.primary_key]),
    )
