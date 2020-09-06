import requests
from knife.test import TestCase, SERVER


def clear_recipes():
    query = requests.get("%s/dishes" % SERVER)
    for recipe in query.json().get('data'):
        requests.delete("%s/dishes/%s" % (SERVER, recipe.get('id')))


class TestDishIndex(TestCase):
    def setUp(self):
        endpoint = 'dishes'
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
        filters = {'name': 'Tartare'}
        query = requests.get(self.url, params=filters)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), list)

    def test_index_author_search(self):
        filters = {'author': 'jb'}
        query = requests.get(self.url, params=filters)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), list)

    def test_index_directions_search(self):
        filters = {'directions': 'do stuff'}
        query = requests.get(self.url, params=filters)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), list)

    def test_index_mixed_search(self):
        filters = {'author': 'jb', 'name': 'Tartare'}
        query = requests.get(self.url, params=filters)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), list)

    def test_index_wrong_field_search(self):
        filters = {'wrong_field': 'Tartare'}
        query = requests.get(self.url, params=filters)

        self.assertFalse(query.ok, msg=query.json())

    def test_index_wrong_mixed_search(self):
        filters = {'author': 'jb', 'wrong_field': 'Tartare'}
        query = requests.get(self.url, params=filters)

        self.assertFalse(query.ok, msg=query.json())


class TestDishCreate(TestCase):
    def setUp(self):
        endpoint = 'dishes/new'
        self.url = "%s/%s" % (SERVER, endpoint)

        clear_recipes()

    def tearDown(self):
        clear_recipes()

    def test_create_name(self):
        params = {'name': 'Tartare'}
        query = requests.post(self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), dict)
        self.assertIsInstance(query.json().get('data').get('id'), str)

    def test_create_full(self):
        params = {'name': 'Tartare', 'author': 'jb', 'directions': 'Do stuff'}
        query = requests.post(self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), dict)
        self.assertIsInstance(query.json().get('data').get('id'), str)

    def test_create_no_name(self):
        params = {'author': 'jb'}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_create_same(self):
        params = {'name': 'Tartare'}
        query = requests.post(self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), dict)
        self.assertIsInstance(query.json().get('data').get('id'), str)

        params = {'name': 'Tartare'}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_create_wrong_params(self):
        params = {
            'name': 'Tartare',
            'author': 'jb',
            'directions': 'Do stuff',
            'metadata': 'stuff'
        }
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_create_empty(self):
        params = {'name': ''}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())


class TestDishDelete(TestCase):
    def setUp(self):
        clear_recipes()
        query = requests.post("%s/dishes/new" % SERVER,
                              data={'name': 'Tartare'})
        dish_id = query.json().get('data').get('id')

        endpoint = "/dishes/%s" % dish_id
        self.url = "%s/%s" % (SERVER, endpoint)

    def tearDown(self):
        clear_recipes()

    def test_delete(self):
        query = requests.delete(self.url)

        self.assertTrue(query.ok, msg=query.json())

    def test_delete_nonexistent(self):
        query = requests.delete(self.url)
        query = requests.delete(self.url)

        self.assertFalse(query.ok, msg=query.json())


class TestDishEdit(TestCase):
    def setUp(self):
        clear_recipes()
        query = requests.post("%s/dishes/new" % SERVER,
                              data={'name': 'Tartare'})
        dish_id = query.json().get('data').get('id')

        endpoint = "/dishes/%s" % dish_id
        self.url = "%s/%s" % (SERVER, endpoint)

    def tearDown(self):
        clear_recipes()

    def test_edit_name(self):
        new_name = 'Tartare Francais'
        query = requests.put(self.url, data={'name': new_name})

        self.assertTrue(query.ok, msg=query.json())

        query = requests.get(self.url)

        self.assertTrue(query.ok, msg=query.json())
        self.assertEqual(query.json().get('data').get('name'), new_name)

    def test_edit_author(self):
        new_author = 'jb'
        query = requests.put(self.url, data={'author': new_author})

        self.assertTrue(query.ok, msg=query.json())

        query = requests.get(self.url)

        self.assertTrue(query.ok, msg=query.json())
        self.assertEqual(query.json().get('data').get('author'), new_author)

    def test_edit_directions(self):
        new_directions = 'do stuff'
        query = requests.put(self.url, data={'directions': new_directions})

        self.assertTrue(query.ok, msg=query.json())

        query = requests.get(self.url)

        self.assertTrue(query.ok, msg=query.json())
        self.assertEqual(query.json().get('data').get('directions'),
                         new_directions)

    def test_edit_mixed(self):
        new_author = 'jb'
        new_directions = 'do stuff'
        query = requests.put(self.url,
                             data={
                                 'directions': new_directions,
                                 'author': new_author
                             })

        self.assertTrue(query.ok, msg=query.json())

        query = requests.get(self.url)

        self.assertTrue(query.ok, msg=query.json())
        self.assertEqual(query.json().get('data').get('directions'),
                         new_directions)
        self.assertEqual(query.json().get('data').get('author'), new_author)

    def test_edit_name_invalid(self):
        new_name = ''
        query = requests.put(self.url, data={'name': new_name})

        self.assertFalse(query.ok, msg=query.json())

        query = requests.get(self.url)

        self.assertTrue(query.ok, msg=query.json())
        self.assertNotEqual(query.json().get('data').get('name'), new_name)

    def test_edit_name_taken(self):
        new_name = 'Tartare Francais'
        query = requests.post("%s/dishes/new" % SERVER,
                              data={'name': new_name})
        self.assertTrue(query.ok, msg=query.json())

        query = requests.put(self.url, data={'name': new_name})
        self.assertFalse(query.ok, msg=query.json())

        query = requests.get(self.url)
        self.assertTrue(query.ok, msg=query.json())
        self.assertNotEqual(query.json().get('data').get('name'), new_name)

    def test_edit_nonexistent(self):
        new_name = 'Tartare Francais'
        query = requests.put(self.url+'_bis', data={'name': new_name})
        self.assertFalse(query.ok, msg=query.json())

class TestDishShow(TestCase):
    def setUp(self):
        clear_recipes()
        query = requests.post("%s/dishes/new" % SERVER,
                              data={
                                  'name': 'Tartare',
                                  'author': 'jb',
                                  'directions': 'Grind the meat.'
                              })
        dish_id = query.json().get('data').get('id')

        endpoint = "/dishes/%s" % dish_id
        self.url = "%s/%s" % (SERVER, endpoint)

    def tearDown(self):
        clear_recipes()

    def test_show_fields(self):
        query = requests.get(self.url)
        self.assertTrue(query.ok, msg=query.json())
        self.assertIn('id', query.json().get('data'))
        self.assertIn('name', query.json().get('data'))
        self.assertIn('author', query.json().get('data'))
        self.assertIn('directions', query.json().get('data'))
        self.assertIn('requirements', query.json().get('data'))
        self.assertIn('tags', query.json().get('data'))
        self.assertIn('dependencies', query.json().get('data'))

    def test_show_nonexistent(self):
        query = requests.get(self.url+'_bis')
        self.assertFalse(query.ok, msg=query.json())
