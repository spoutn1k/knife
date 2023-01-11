from knife.models.knife_model import KnifeModel, Datatypes, FieldList, Field


class Ingredient(KnifeModel):
    table_name = 'ingredients'
    fields = FieldList(
        Field(name='id', datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field(name='name', datatype=[Datatypes.TEXT]),
        Field(name='simple_name', datatype=[Datatypes.TEXT]),
    )

    def __init__(self, params):
        self._id = params.get("id")
        self.name = params.get("name", '').rstrip()
