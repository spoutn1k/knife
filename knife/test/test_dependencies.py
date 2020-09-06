import requests
from knife.test import TestCase, SERVER

RECIPE_NAMES = ('Tartare', 'Frites')
RECIPE_IDS = []


def create_objects():
    global RECIPE_IDS

    for name in RECIPE_NAMES:
        query = requests.post("%s/dishes/new" % SERVER, data={'name': name})
        RECIPE_IDS.append(query.json().get('data').get('id'))


def delete_objects():
    global RECIPE_IDS

    clear_dependencies()

    for id in RECIPE_IDS:
        requests.delete("%s/dishes/%s" % (SERVER, id))

    RECIPE_IDS = []


def clear_dependencies():
    for id in RECIPE_IDS:
        for dep in requests.get("%s/dishes/%s/dependencies" %
                                (SERVER, id)).json().get('data'):
            requests.delete("%s/dishes/%s/dependencies/%s" %
                            (SERVER, id, dep.get('id')))


class TestDependencyShow(TestCase):
    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        self.url = "%s/dishes/%s/dependencies" % (SERVER, RECIPE_IDS[0])

    def test_index_all(self):
        params = {'requisite': RECIPE_IDS[1]}
        query = requests.post("%s/add" % self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())

        query = requests.get(self.url)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), list)


class TestDependencyAdd(TestCase):
    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        self.url = "%s/dishes/%s/dependencies/add" % (SERVER, RECIPE_IDS[0])
        clear_dependencies()

    def test_add(self):
        params = {'requisite': RECIPE_IDS[1]}
        query = requests.post(self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())

    def test_add_no_recipe(self):
        params = {}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_add_same(self):
        params = {'requisite': RECIPE_IDS[1]}
        query = requests.post(self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())

        params = {'requisite': RECIPE_IDS[1]}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_add_wrong_field(self):
        params = {'ingredient': 'Nonexistsent'}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_add_invalid_recipe(self):
        params = {'requisite': 'nonexistent'}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_add_cycle(self):
        params = {'requisite': RECIPE_IDS[1]}
        query = requests.post(self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())

        url = "%s/dishes/%s/dependencies/add" % (SERVER, RECIPE_IDS[1])
        params = {'requisite': RECIPE_IDS[0]}

        query = requests.post(url, data=params)
        self.assertFalse(query.ok, msg=query.json())

        query = requests.post(self.url, data=params)
        self.assertFalse(query.ok, msg=query.json())

class TestDependencyDelete(TestCase):
    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        self.url = "%s/dishes/%s/dependencies" % (SERVER, RECIPE_IDS[0])

    def test_delete(self):
        params = {'requisite': RECIPE_IDS[1]}
        query = requests.post("%s/add" % self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())

        query = requests.delete("%s/%s" % (self.url, RECIPE_IDS[1]))

        self.assertTrue(query.ok, msg=query.json())

    def test_delete_nonexistent(self):
        query = requests.delete("%s/%s" % (self.url, 'nonexistent'))

        self.assertFalse(query.ok, msg=query.json())
