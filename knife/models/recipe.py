from knife.models.knife_model import KnifeModel, Datatypes, FieldList, Field


class Recipe(KnifeModel):
    table_name = 'recipes'
    fields = FieldList(
        Field(name='id', datatype=[Datatypes.text, Datatypes.primary_key]),
        Field(name='name', datatype=[Datatypes.text]),
        Field(name='simple_name', datatype=[Datatypes.text]),
        Field(name='author', datatype=[Datatypes.text]),
        Field(name='directions', datatype=[Datatypes.text]),
    )

    def __init__(self, params):
        self._id = params.get('id')
        self.name = params.get('name', '').rstrip()
        self.author = params.get('author', '').rstrip()
        self.directions = params.get('directions', '').rstrip()
