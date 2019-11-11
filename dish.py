from unidecode import unidecode
import hashlib

class Dish:
    def __init__(self, params, store=None):
        self._id = params.get('id', None)
        self.name = params.get('name')
        self.author = params.get('author')
        self.directions = params.get('directions')
        self.store = store
        self.requirements = [{'ingredient': store.get_ingredient(data),
                              'quantity': data['quantity']} for data in params.get('ingredients', [])]
        self.dependencies = params.get('dependencies', [])
        self.tags = params.get('tags', [])

    def __str__(self):
        return self.name

    def save(self):
        return self.store.save_dish(self)

    @property
    def id(self):
        m = hashlib.sha256()
        m.update(self.name.encode())
        return m.hexdigest()

    @property
    def simple_name(self):
        return unidecode(self.name.lower()).replace(' ', '_').replace("'", '_')

    @property
    def params(self):
        return {'id': self.id,
                'name': self.name,
                'simple_name': self.simple_name,
                'author': self.author,
                'directions': self.directions,
                'ingredients': self.requirements,
                'tags': self.tags,
                'dependencies': self.dependencies}

    @property
    def json(self):
        return {'id': self.id,
                'name': self.name,
                'author': self.author,
                'directions': self.directions,
                'ingredients': [{'ingredient': {'id': data['ingredient'].id, 'name': data['ingredient'].name}, 'quantity': data['quantity']} for data in self.requirements],
                'tags': [tag.get('name') for tag in self.tags],
                'dependencies': self.dependencies}
