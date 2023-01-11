from knife.models.knife_model import Datatypes, FieldList, Field


class Requirement:
    table_name = 'requirements'
    fields = FieldList(
        Field(name='recipe_id',
              datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field(name='ingredient_id',
              datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field(name='quantity', datatype=[Datatypes.TEXT]),
    )
