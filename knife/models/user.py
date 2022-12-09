import time
from knife import helpers
from knife.models import Datatypes, Attributes, FieldList


class User:
    table_name = 'users'
    fields = FieldList(('id', Datatypes.text, Attributes.primary_key),
                       ('name', Datatypes.text))

    def __init__(self, params):
        self._id = params.get('id')
        self.name = params.get('name', '').rstrip()

    def __str__(self):
        return self.name

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
        }

    @property
    def serializable(self):
        return {
            'id': self.id,
            'name': self.name,
        }
