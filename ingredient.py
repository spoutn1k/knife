import hashlib

class Ingredient:
    name = ''
    _id = 0

    def __init__(self, params, store):
        self._id = params.get("id")
        self.name = params["name"]

    @property
    def id(self):
        m = hashlib.sha256()
        m.update(self.name.encode())
        return m.hexdigest()

    @property
    def params(self):
        return {'id': self.id,
                'name': self.name,
                'unit': int(self.default_unit)}
