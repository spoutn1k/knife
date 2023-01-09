from knife.models.knife_model import KnifeModel, Datatypes, FieldList, Field


class Ingredient(KnifeModel):
    table_name = 'ingredients'
    fields = FieldList(
        Field(name='id', datatype=[Datatypes.text, Datatypes.primary_key]),
        Field(name='name', datatype=[Datatypes.text]),
        Field(name='simple_name', datatype=[Datatypes.text]),
    )

    def __init__(self, params):
        self._id = params.get("id")
        self.name = params.get("name", '').rstrip()
