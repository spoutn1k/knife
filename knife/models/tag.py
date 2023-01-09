from knife.models.knife_model import Datatypes, FieldList, Field


class Tag:
    table_name = 'tags'
    fields = FieldList(
        Field(name='recipe_id',
              datatype=[Datatypes.text, Datatypes.primary_key]),
        Field(name='label_id',
              datatype=[Datatypes.text, Datatypes.primary_key]),
    )
