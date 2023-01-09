from knife.models.knife_model import Datatypes, FieldList, Field


class Requirement:
    table_name = 'requirements'
    fields = FieldList(
        Field(name='recipe_id',
              datatype=[Datatypes.text, Datatypes.primary_key]),
        Field(name='ingredient_id',
              datatype=[Datatypes.text, Datatypes.primary_key]),
        Field(name='quantity', datatype=[Datatypes.text]),
    )
