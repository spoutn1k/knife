from knife.models.knife_model import (Datatypes, FieldList, Field, KnifeModel)


class Requirement(KnifeModel):
    table_name = 'requirements'
    fields = FieldList(
        Field(name='recipe_id',
              datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field(name='ingredient_id',
              datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field(name='quantity', datatype=[Datatypes.TEXT]),
        Field(name='optional', datatype=[Datatypes.BOOLEAN], default=False),
        Field(name='group', datatype=[Datatypes.TEXT], default=""),
    )
