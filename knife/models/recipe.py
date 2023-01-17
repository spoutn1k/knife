from knife.models.knife_model import KnifeModel, Datatypes, FieldList, Field


class Recipe(KnifeModel):
    table_name = 'recipes'
    fields = FieldList(
        Field(name='id', datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field(name='name', datatype=[Datatypes.TEXT]),
        Field(name='simple_name', datatype=[Datatypes.TEXT]),
        Field(name='author', datatype=[Datatypes.TEXT], default=""),
        Field(name='directions', datatype=[Datatypes.TEXT], default=""),
        Field(name='information', datatype=[Datatypes.TEXT], default=""),
    )

    def serializable(self, **kwargs):
        return kwargs | super().serializable
