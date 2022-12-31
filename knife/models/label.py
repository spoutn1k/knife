import time
from knife import helpers
from knife.models import Datatypes, FieldList, Field


class Label:
    table_name = 'labels'
    fields = FieldList(
        Field('id', datatype=[Datatypes.text, Datatypes.primary_key]),
        Field('name', datatype=[Datatypes.text]),
        Field('simple_name', datatype=[Datatypes.text]),
    )

    def __init__(self, params):
        self._id = params.get("id")
        self.name = params.get("name", '').rstrip()

    @property
    def id(self):
        if not self._id:
            self._id = helpers.hash256("{}{}".format(self.name, time.time()))
        return self._id

    @property
    def simple_name(self):
        return helpers.simplify(self.name)

    @property
    def params(self):
        return {
            'id': self.id,
            'name': self.name,
            'simple_name': self.simple_name
        }

    @property
    def serializable(self):
        return {'id': self.id, 'name': self.name}
