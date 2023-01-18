import requests
from test.api import APITestCase, SERVER

RECIPE_NAME = 'Tartare'
RECIPE_ID = 'Not set'

INGREDIENT_NAMES = ('Oignon', 'Cornichon')
INGREDIENT_IDS = []


def create_objects():
    global RECIPE_ID
    global INGREDIENT_IDS

    query = requests.post("%s/recipes/new" % SERVER,
                          json={'name': RECIPE_NAME})
    RECIPE_ID = query.json().get('data').get('id')

    for name in INGREDIENT_NAMES:
        query = requests.post("%s/ingredients/new" % SERVER,
                              json={'name': name})
        INGREDIENT_IDS.append(query.json().get('data').get('id'))


def delete_objects():
    global RECIPE_ID
    global INGREDIENT_IDS

    for id in INGREDIENT_IDS:
        requests.delete("%s/recipes/%s/requirements/%s" %
                        (SERVER, RECIPE_ID, id))
        requests.delete("%s/ingredients/%s" % (SERVER, id))

    INGREDIENT_IDS = []

    requests.delete("%s/recipes/%s" % (SERVER, RECIPE_ID))


def default_requirements():
    requests.post("%s/recipes/%s/requirements/add" % (SERVER, RECIPE_ID),
                  json={
                      'ingredient_id': INGREDIENT_IDS[0],
                      'quantity': 4
                  })


def clear_requirements():
    query = requests.get("%s/recipes/%s/requirements" % (SERVER, RECIPE_ID))
    for requirement in query.json().get('data'):
        requests.delete(
            "%s/recipes/%s/requirements/%s" %
            (SERVER, RECIPE_ID, requirement.get('ingredient').get('id')))


class TestRequirementShow(APITestCase):

    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        clear_requirements()
        self.url = "%s/recipes/%s/requirements" % (SERVER, RECIPE_ID)
        default_requirements()

    def tearDown(self):
        clear_requirements()

    def test_index_all(self):
        query = requests.get(self.url)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), list)


class TestRequirementAdd(APITestCase):

    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        clear_requirements()
        self.url = "%s/recipes/%s/requirements/add" % (SERVER, RECIPE_ID)
        default_requirements()

    def tearDown(self):
        clear_requirements()

    def test_add(self):
        params = {'ingredient_id': INGREDIENT_IDS[1], 'quantity': 3}
        query = requests.post(self.url, json=params)

        self.assertTrue(query.ok, msg=query.json())

    def test_add_no_ingredient(self):
        params = {'quantity': 3}
        query = requests.post(self.url, json=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_add_no_quantity(self):
        params = {'quantity': 3}
        query = requests.post(self.url, json=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_add_same(self):
        params = {'ingredient_id': INGREDIENT_IDS[0], 'quantity': 3}
        query = requests.post(self.url, json=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_add_wrong_ingredient(self):
        params = {'ingredient': 'Nonexistsent', 'quantity': 3}
        query = requests.post(self.url, json=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_add_wrong_params(self):
        params = {
            'ingredient_id': INGREDIENT_IDS[1],
            'quantity': 3,
            'metadata': 'lol'
        }
        query = requests.post(self.url, json=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_create_empty(self):
        params = {
            'ingredient_id': INGREDIENT_IDS[1],
            'quantity': None,
            'metadata': 'lol'
        }
        query = requests.post(self.url, json=params)

        self.assertFalse(query.ok, msg=query.json())


class TestRequirementDelete(APITestCase):

    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        clear_requirements()
        self.url = "%s/recipes/%s/requirements" % (SERVER, RECIPE_ID)
        default_requirements()

    def tearDown(self):
        clear_requirements()

    def test_delete(self):
        query = requests.delete("%s/%s" % (self.url, INGREDIENT_IDS[0]))

        self.assertTrue(query.ok, msg=query.json())

    def test_delete_nonexistent(self):
        query = requests.delete("%s/%s" % (self.url, 'nonexistent'))

        self.assertFalse(query.ok, msg=query.json())


class TestRequirementEdit(APITestCase):

    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        clear_requirements()
        self.url = "%s/recipes/%s/requirements" % (SERVER, RECIPE_ID)
        default_requirements()

    def tearDown(self):
        clear_requirements()

    def test_edit(self):
        new_quantity = '5 cups'
        query = requests.put("%s/%s" % (self.url, INGREDIENT_IDS[0]),
                             json={'quantity': new_quantity})

        self.assertTrue(query.ok, msg=query.json())

        query = requests.get(self.url)
        self.assertTrue(query.ok, msg=query.json())
        self.assertEqual(new_quantity, query.json()['data'][0]['quantity'])

    def test_edit_nonexistent(self):
        query = requests.put("%s/%s" % (self.url, 'nonexistent'),
                             json={'quantity': 5})

        self.assertFalse(query.ok, msg=query.json())

    def test_edit_invalid_quantity(self):
        new_quantity = ''
        query = requests.put("%s/%s" % (self.url, INGREDIENT_IDS[0]),
                             json={'quantity': new_quantity})

        self.assertFalse(query.ok, msg=query.json())

        query = requests.get(self.url)
        self.assertTrue(query.ok, msg=query.json())
        self.assertNotEqual(new_quantity, query.json()['data'][0]['quantity'])

    def test_edit_wrong_field(self):
        new_quantity = '5 cups'
        query = requests.put("%s/%s" % (self.url, INGREDIENT_IDS[0]),
                             json={'quantitad': new_quantity})

        self.assertFalse(query.ok, msg=query.json())

        query = requests.put("%s/%s" % (self.url, INGREDIENT_IDS[0]),
                             json={
                                 'quantity': new_quantity,
                                 'metadata': False
                             })

        self.assertFalse(query.ok, msg=query.json())

        query = requests.get(self.url)
        self.assertTrue(query.ok, msg=query.json())
        self.assertNotEqual(new_quantity, query.json()['data'][0]['quantity'])
