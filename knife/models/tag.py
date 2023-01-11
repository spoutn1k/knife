from knife.models.knife_model import Datatypes, FieldList, Field


class Tag:
    table_name = 'tags'
    fields = FieldList(
        Field(name='recipe_id',
              datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field(name='label_id',
              datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
    )
