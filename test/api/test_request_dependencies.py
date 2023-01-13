import requests
from test.api import APITestCase, SERVER

RECIPE_NAMES = ('Tartare', 'Frites')
RECIPE_IDS = []


def create_objects():
    global RECIPE_IDS

    for name in RECIPE_NAMES:
        query = requests.post("%s/recipes/new" % SERVER, data={'name': name})
        RECIPE_IDS.append(query.json().get('data').get('id'))


def delete_objects():
    global RECIPE_IDS

    clear_dependencies()

    for id in RECIPE_IDS:
        requests.delete("%s/recipes/%s" % (SERVER, id))

    RECIPE_IDS = []


def clear_dependencies():
    for id in RECIPE_IDS:
        for dep in requests.get("%s/recipes/%s/dependencies" %
                                (SERVER, id)).json().get('data'):
            recipe_id = dep.get('recipe').get('id')
            requests.delete("%s/recipes/%s/dependencies/%s" %
                            (SERVER, id, recipe_id))


class TestDependencyShow(APITestCase):

    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        self.url = "%s/recipes/%s/dependencies" % (SERVER, RECIPE_IDS[0])
        clear_dependencies()

    def test_index_all(self):
        params = {'requisite': RECIPE_IDS[1]}
        query = requests.post("%s/add" % self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())

        query = requests.get(self.url)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), list)


class TestDependencyAdd(APITestCase):

    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        self.url = "%s/recipes/%s/dependencies/add" % (SERVER, RECIPE_IDS[0])
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

        url = "%s/recipes/%s/dependencies/add" % (SERVER, RECIPE_IDS[1])
        params = {'requisite': RECIPE_IDS[0]}
        query = requests.post(url, data=params)

        self.assertFalse(query.ok, msg=query.json())

        query = requests.post(self.url, data=params)
        self.assertFalse(query.ok, msg=query.json())


class TestDependencyEdit(APITestCase):

    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        self.url = "%s/recipes/%s/dependencies" % (SERVER, RECIPE_IDS[0])
        clear_dependencies()

    def test_edit_quantity(self):
        params = dict(
            requisite=RECIPE_IDS[1],
            quantity='A ton',
        )
        query = requests.post(f"{self.url}/add", data=params)
        self.assertTrue(query.ok, msg='')

        params = {'quantity': 'some amount'}
        query = requests.put(f"{self.url}/{RECIPE_IDS[1]}", data=params)
        self.assertTrue(query.ok,
                        msg=f"Status code {query.status_code} returned")

        query = requests.get(f"{self.url}")
        self.assertTrue(query.ok,
                        msg=f"Status code {query.status_code} returned")
        data = list(
            filter(
                lambda x: x.get('recipe', {}).get('id', '') == RECIPE_IDS[1],
                query.json()['data'],
            ))

        self.assertEqual(len(data), 1)
        self.assertEqual(
            data[0],
            data[0] | {'quantity': 'some amount'},
        )

    def test_edit_optional(self):
        params = dict(
            requisite=RECIPE_IDS[1],
            optional=True,
        )
        query = requests.post(f"{self.url}/add", data=params)
        self.assertTrue(query.ok)

        params = dict(optional=False)
        query = requests.put(f"{self.url}/{RECIPE_IDS[1]}", data=params)
        self.assertTrue(query.ok,
                        msg=f"Status code {query.status_code} returned")

        query = requests.get(f"{self.url}")
        self.assertTrue(query.ok,
                        msg=f"Status code {query.status_code} returned")
        data = list(
            filter(
                lambda x: x.get('recipe', {}).get('id', '') == RECIPE_IDS[1],
                query.json()['data'],
            ))

        self.assertEqual(len(data), 1)
        self.assertEqual(
            data[0],
            data[0] | dict(optional=False),
        )


class TestDependencyDelete(APITestCase):

    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        self.url = "%s/recipes/%s/dependencies" % (SERVER, RECIPE_IDS[0])
        clear_dependencies()

    def test_delete(self):
        params = {'requisite': RECIPE_IDS[1]}
        query = requests.post("%s/add" % self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())

        query = requests.delete("%s/%s" % (self.url, RECIPE_IDS[1]))

        self.assertTrue(query.ok, msg=query.json())

    def test_delete_nonexistent(self):
        query = requests.delete("%s/%s" % (self.url, 'nonexistent'))

        self.assertFalse(query.ok, msg=query.json())
