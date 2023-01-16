from knife.models.knife_model import KnifeModel, Datatypes, FieldList, Field


class Ingredient(KnifeModel):
    table_name = 'ingredients'
    fields = FieldList(
        Field(name='id', datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field(name='name', datatype=[Datatypes.TEXT]),
        Field(name='simple_name', datatype=[Datatypes.TEXT]),
        Field(name='dairy', datatype=[Datatypes.BOOLEAN], default=False),
        Field(name='gluten', datatype=[Datatypes.BOOLEAN], default=False),
        Field(name='meat', datatype=[Datatypes.BOOLEAN], default=False),
        Field(name='animal-product',
              datatype=[Datatypes.BOOLEAN],
              default=False),
    )
