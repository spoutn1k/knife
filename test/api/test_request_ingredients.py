import requests
from test.api import APITestCase, SERVER


def clear_ingredients():
    query = requests.get("%s/ingredients" % SERVER)
    for ingredient in query.json().get('data'):
        requests.delete("%s/ingredients/%s" % (SERVER, ingredient.get('id')))


class TestIngredientIndex(APITestCase):

    def setUp(self):
        endpoint = 'ingredients'
        self.url = "%s/%s" % (SERVER, endpoint)

    def test_index_all(self):
        query = requests.get(self.url)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), list)

    def test_index_id_search(self):
        filters = {'id': 'test'}
        query = requests.get(self.url, params=filters)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), list)

    def test_index_name_search(self):
        filters = {'name': 'Oignon'}
        query = requests.get(self.url, params=filters)

        self.assertTrue(query.status_code)
        self.assertIsInstance(query.json().get('data'), list)

    def test_index_mixed_search(self):
        filters = {'id': 'hex', 'name': 'Oignon'}
        query = requests.get(self.url, params=filters)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), list)

    def test_index_wrong_field_search(self):
        filters = {'wrong_field': 'Oignon'}
        query = requests.get(self.url, params=filters)

        self.assertFalse(query.ok, msg=query.json())

    def test_index_wrong_mixed_search(self):
        filters = {'name': 'Oignon', 'wrong_field': 'stuff'}
        query = requests.get(self.url, params=filters)

        self.assertFalse(query.ok, msg=query.json())


class TestIngredientCreate(APITestCase):

    def setUp(self):
        endpoint = 'ingredients/new'
        self.url = "%s/%s" % (SERVER, endpoint)

        clear_ingredients()

    def tearDown(self):
        clear_ingredients()

    def test_create_name(self):
        params = {'name': 'Oignon'}
        query = requests.post(self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), dict)
        self.assertIsInstance(query.json().get('data').get('id'), str)

    def test_create_no_name(self):
        params = {}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_create_same(self):
        params = {'name': 'Oignon'}
        query = requests.post(self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), dict)
        self.assertIsInstance(query.json().get('data').get('id'), str)

        params = {'name': 'Oignon'}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_create_wrong_params(self):
        params = {'name': 'Oignon', 'metadata': 'stuff'}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_create_empty(self):
        params = {'name': ''}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())


class TestIngredientDelete(APITestCase):

    def setUp(self):
        clear_ingredients()
        query = requests.post("%s/ingredients/new" % SERVER,
                              data={'name': 'Oignon'})
        ingredient_id = query.json().get('data').get('id')

        endpoint = "/ingredients/%s" % ingredient_id
        self.url = "%s/%s" % (SERVER, endpoint)

    def tearDown(self):
        clear_ingredients()

    def test_delete(self):
        query = requests.delete(self.url)

        self.assertTrue(query.ok, msg=query.json())

    def test_delete_nonexistent(self):
        query = requests.delete(self.url)
        query = requests.delete(self.url)

        self.assertFalse(query.ok, msg=query.json())


class TestIngredientEdit(APITestCase):

    def setUp(self):
        clear_ingredients()
        query = requests.post("%s/ingredients/new" % SERVER,
                              data={'name': 'Oignon'})
        ingredient_id = query.json().get('data').get('id')

        endpoint = "/ingredients/%s" % ingredient_id
        self.url = "%s/%s" % (SERVER, endpoint)

    def tearDown(self):
        clear_ingredients()

    def test_edit_name(self):
        new_name = 'Oignon Francais'
        query = requests.put(self.url, data={'name': new_name})

        self.assertTrue(query.ok, msg=query.json())

        query = requests.get("%s/ingredients" % SERVER,
                             params={'name': new_name})

        self.assertTrue(query.ok, msg=query.json())
        self.assertEqual(query.json().get('data')[0].get('name'), new_name)

    def test_edit_name_invalid(self):
        new_name = ''
        query = requests.put(self.url, data={'name': new_name})

        self.assertFalse(query.ok, msg=query.json())

        query = requests.get(self.url)

        self.assertTrue(query.ok, msg=query.json())
        self.assertNotEqual(query.json().get('data').get('name'), new_name)

    def test_edit_name_taken(self):
        new_name = 'Oignon Francais'
        query = requests.post("%s/ingredients/new" % SERVER,
                              data={'name': new_name})
        self.assertTrue(query.ok, msg=query.json())

        query = requests.put(self.url, data={'name': new_name})
        self.assertFalse(query.ok, msg=query.json())

        query = requests.get(self.url)
        self.assertTrue(query.ok, msg=query.json())
        self.assertNotEqual(query.json().get('data').get('name'), new_name)

    def test_edit_nonexistent(self):
        new_name = 'Oignon Francais'
        query = requests.put(self.url + '_bis', data={'name': new_name})
        self.assertFalse(query.ok, msg=query.json())
