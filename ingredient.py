from enum import IntEnum, auto
import hashlib

class Units(IntEnum):
    WHOLE = 0
    GRAM = 10
    KILOGRAM = 11
    MILLILITER = 10
    CENTILITER = 21
    LITER = 22
    TEASPOON = 30
    TABLESPOON = 31

class ingredient:
    name = ''
    default_unit = Units.WHOLE
    _id = 0
    references = 0

    def __init__(self, params):
        self._id = params.get("_id", None)
        self.name = params.get("name")
        #self.default_unit = Units(params["unit"])

    @property
    def id(self):
        m = hashlib.sha256()
        m.update(self.name.encode())
        return m.hexdigest()

    @property
    def params(self):
        return {'_id': self.id,
                'name': self.name,
                'unit': int(self.default_unit)}
