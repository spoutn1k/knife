from knife.models import Datatypes, FieldList


class Dependency:
    table_name = 'dependencies'
    fields = FieldList(('required_by', Datatypes.text, Datatypes.primary_key),
                       ('requisite', Datatypes.text, Datatypes.primary_key),
                       ('quantity', Datatypes.text))
