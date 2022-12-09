from knife.models import Datatypes, Attributes, FieldList


class Dependency:
    table_name = 'dependencies'
    fields = FieldList(('required_by', Datatypes.text, Attributes.primary_key),
                       ('requisite', Datatypes.text, Attributes.primary_key))
