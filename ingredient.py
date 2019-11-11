import json
import hashlib

class Ingredient:
    name = ''
    _id = 0

    def __init__(self, params, store):
        self._id = params.get("id")
        self.name = params["name"]
        self.store = store

    @property
    def id(self):
        m = hashlib.sha256()
        m.update(self.name.encode())
        return m.hexdigest()

    @property
    def params(self):
        return {'id': self.id,
                'name': self.name}

    @property
    def json(self):
        return json.dumps(self.params)

    def save(self):
        return self.store.save_ingredient(self)
