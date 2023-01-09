from knife.models.knife_model import Datatypes, FieldList, Field


class Dependency:
    table_name = 'dependencies'
    fields = FieldList(
        Field(name='required_by',
              datatype=[Datatypes.text, Datatypes.primary_key]),
        Field(name='requisite',
              datatype=[Datatypes.text, Datatypes.primary_key]),
        Field(name='quantity', datatype=[Datatypes.text], default=""),
    )
