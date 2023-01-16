from knife.models.knife_model import KnifeModel, Datatypes, FieldList, Field


class Label(KnifeModel):
    table_name = 'labels'
    fields = FieldList(
        Field('id', datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field('name', datatype=[Datatypes.TEXT]),
        Field('simple_name', datatype=[Datatypes.TEXT]),
    )
