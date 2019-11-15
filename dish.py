import time
import helpers
from ingredient import Ingredient

class Dish:
    def __init__(self, params):
        self._id = params.get('id')
        self.name = params.get('name')
        self.author = params.get('author')
        self.directions = params.get('directions')
        self.requirements = []
        for data in params.get('requirements', []):
            ing = Ingredient(data.get('ingredient'))
            self.requirements.append({'ingredient': ing, 'quantity': data['quantity']})
        self.dependencies = params.get('dependencies', [])
        self.tags = params.get('tags', [])

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
        return {'id': self.id,
                'name': self.name,
                'simple_name': self.simple_name,
                'author': self.author,
                'directions': self.directions,
                'requirements': self.requirements,
                'tags': self.tags,
                'dependencies': self.dependencies}

    @property
    def serializable(self):
        return {'id': self.id,
                'name': self.name,
                'author': self.author,
                'directions': self.directions,
                'requirements': [{'ingredient': {'id': data['ingredient'].id,
                                                 'name': data['ingredient'].name},
                                  'quantity': data['quantity']} for data in self.requirements],
                'tags': self.tags,
                'dependencies': self.dependencies}
