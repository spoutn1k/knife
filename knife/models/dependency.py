from knife.models.knife_model import Datatypes, FieldList, Field


class Dependency:
    table_name = 'dependencies'
    fields = FieldList(
        Field(name='required_by',
              datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field(name='requisite',
              datatype=[Datatypes.TEXT, Datatypes.PRIMARY_KEY]),
        Field(name='quantity', datatype=[Datatypes.TEXT], default=""),
        Field(name='optional', datatype=[Datatypes.BOOLEAN], default=False),
    )
