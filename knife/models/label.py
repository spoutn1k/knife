from knife.models.knife_model import KnifeModel, Datatypes, FieldList, Field


class Label(KnifeModel):
    table_name = 'labels'
    fields = FieldList(
        Field('id', datatype=[Datatypes.text, Datatypes.primary_key]),
        Field('name', datatype=[Datatypes.text]),
        Field('simple_name', datatype=[Datatypes.text]),
    )

    def __init__(self, params):
        self._id = params.get("id")
        self.name = params.get("name", '').rstrip()
