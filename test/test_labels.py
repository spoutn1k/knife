import requests
from test import TestCase, SERVER


def clear_labels():
    query = requests.get("%s/labels" % SERVER)
    for label in query.json().get('data'):
        requests.delete("%s/labels/%s" % (SERVER, label.get('id')))


class TestLabelIndex(TestCase):

    def setUp(self):
        endpoint = 'labels'
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
        filters = {'name': 'french'}
        query = requests.get(self.url, params=filters)

        self.assertTrue(query.status_code)
        self.assertIsInstance(query.json().get('data'), list)

    def test_index_mixed_search(self):
        filters = {'id': 'hex', 'name': 'french'}
        query = requests.get(self.url, params=filters)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), list)

    def test_index_wrong_field_search(self):
        filters = {'wrong_field': 'french'}
        query = requests.get(self.url, params=filters)

        self.assertFalse(query.ok, msg=query.json())

    def test_index_wrong_mixed_search(self):
        filters = {'name': 'french', 'wrong_field': 'stuff'}
        query = requests.get(self.url, params=filters)

        self.assertFalse(query.ok, msg=query.json())


class TestLabelCreate(TestCase):

    def setUp(self):
        endpoint = 'labels/new'
        self.url = "%s/%s" % (SERVER, endpoint)

        clear_labels()

    def tearDown(self):
        clear_labels()

    def test_create_name(self):
        params = {'name': 'french'}
        query = requests.post(self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), dict)
        self.assertIsInstance(query.json().get('data').get('id'), str)

    def test_create_no_name(self):
        params = {}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_create_same(self):
        params = {'name': 'french'}
        query = requests.post(self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), dict)
        self.assertIsInstance(query.json().get('data').get('id'), str)

        params = {'name': 'french'}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_create_wrong_params(self):
        params = {'name': 'french', 'metadata': 'stuff'}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_create_empty(self):
        params = {'name': ''}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())


class TestLabelDelete(TestCase):

    def setUp(self):
        clear_labels()
        query = requests.post("%s/labels/new" % SERVER,
                              data={'name': 'french'})
        label_id = query.json().get('data').get('id')

        endpoint = "/labels/%s" % label_id
        self.url = "%s/%s" % (SERVER, endpoint)

    def tearDown(self):
        clear_labels()

    def test_delete(self):
        query = requests.delete(self.url)

        self.assertTrue(query.ok, msg=query.json())

    def test_delete_nonexistent(self):
        query = requests.delete(self.url)
        query = requests.delete(self.url)

        self.assertFalse(query.ok, msg=query.json())


class TestLabelEdit(TestCase):

    def setUp(self):
        clear_labels()
        query = requests.post("%s/labels/new" % SERVER,
                              data={'name': 'french'})
        label_id = query.json().get('data').get('id')

        endpoint = "/labels/%s" % label_id
        self.url = "%s/%s" % (SERVER, endpoint)

    def tearDown(self):
        clear_labels()

    def test_edit_name(self):
        new_name = 'francais'
        query = requests.put(self.url, data={'name': new_name})

        self.assertTrue(query.ok, msg=query.json())

        query = requests.get("%s/labels" % SERVER, params={'name': new_name})

        self.assertTrue(query.ok, msg=query.json())
        self.assertEqual(query.json().get('data')[0].get('name'), new_name)

    def test_edit_name_invalid(self):
        new_name = ''
        query = requests.put(self.url, data={'name': new_name})
        self.assertFalse(query.ok, msg=query.json())

        query = requests.get(self.url)
        self.assertTrue(query.ok, msg=query.json())
        self.assertNotEqual(query.json().get('data').get('name'), new_name)

        new_name = 'name with space'
        query = requests.put(self.url, data={'name': new_name})
        self.assertFalse(query.ok, msg=query.json())

    def test_edit_name_taken(self):
        new_name = 'français'
        query = requests.post("%s/labels/new" % SERVER,
                              data={'name': new_name})
        self.assertTrue(query.ok, msg=query.json())

        query = requests.put(self.url, data={'name': new_name})
        self.assertFalse(query.ok, msg=query.json())

        query = requests.get(self.url)
        self.assertTrue(query.ok, msg=query.json())
        self.assertNotEqual(query.json().get('data').get('name'), new_name)

    def test_edit_nonexistent(self):
        new_name = 'Francais'
        query = requests.put(self.url + '_bis', data={'name': new_name})
        self.assertFalse(query.ok, msg=query.json())
