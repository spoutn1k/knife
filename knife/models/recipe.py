from knife.models.knife_model import KnifeModel, Datatypes, FieldList, Field


class Recipe(KnifeModel):
    table_name = 'recipes'
    fields = FieldList(
        Field(name='id', datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field(name='name', datatype=[Datatypes.TEXT]),
        Field(name='simple_name', datatype=[Datatypes.TEXT]),
        Field(name='author', datatype=[Datatypes.TEXT]),
        Field(name='directions', datatype=[Datatypes.TEXT]),
    )

    def __init__(self, params):
        self._id = params.get('id')
        self.name = params.get('name', '').rstrip()
        self.author = params.get('author', '').rstrip()
        self.directions = params.get('directions', '').rstrip()
