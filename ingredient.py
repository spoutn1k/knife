import time
import helpers

class Ingredient:
    name = ''
    _id = 0

    def __init__(self, params, store):
        self._id = params.get("id")
        self.name = params.get("name")
        self.store = store

    @property
    def id(self):
        if not self._id:
            self._id = helpers.hash256("{}{}".format(self.name, time.time()))
        return self._id

    @property
    def params(self):
        return {'id': self.id,
                'name': self.name}

    @property
    def serializable(self):
        return self.params

    def save(self):
        return self.store.save_ingredient(self)
