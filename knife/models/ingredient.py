import time
from knife import helpers

class Ingredient:
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
        return {'id': self.id,
                'name': self.name,
                'simple_name': self.simple_name}

    @property
    def serializable(self):
        return {'id': self.id,
                'name': self.name}
