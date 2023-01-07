from knife.models import Datatypes, FieldList, Field


class Dependency:
    table_name = 'dependencies'
    fields = FieldList(
        Field(name='required_by',
              datatype=[Datatypes.text, Datatypes.primary_key]),
        Field(name='requisite',
              datatype=[Datatypes.text, Datatypes.primary_key]),
        Field(name='quantity', datatype=[Datatypes.text], default=""),
    )
