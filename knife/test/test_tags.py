import requests
from knife.test import TestCase, SERVER

RECIPE_NAME = 'Tartare'
RECIPE_ID = 'Not set'

LABEL_NAMES = ('french', 'sweet')
LABEL_IDS = []


def create_objects():
    global RECIPE_ID
    global LABEL_IDS

    query = requests.post("%s/recipes/new" % SERVER, data={'name': RECIPE_NAME})
    RECIPE_ID = query.json().get('data').get('id')

    requests.post("%s/recipes/%s/tags/add" % (SERVER, RECIPE_ID),
                  data={
                      'name': LABEL_NAMES[0],
                  })

    query = requests.get("%s/recipes/%s/tags" % (SERVER, RECIPE_ID))

    LABEL_IDS = [l.get('id') for l in query.json()['data']]


def delete_objects():
    global RECIPE_ID
    global LABEL_IDS

    clear_tags()

    for id in LABEL_IDS:
        requests.delete("%s/recipes/%s/tags/%s" % (SERVER, RECIPE_ID, id))
        requests.delete("%s/labels/%s" % (SERVER, id))

    LABEL_IDS = []

    requests.delete("%s/recipes/%s" % (SERVER, RECIPE_ID))


def clear_tags():
    query = requests.get("%s/recipes/%s/tags" % (SERVER, RECIPE_ID))
    for tag in query.json().get('data'):
        requests.delete(
            "%s/recipes/%s/tags/%s" %
            (SERVER, RECIPE_ID, tag.get('id')))


class TestTagShow(TestCase):
    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        self.url = "%s/recipes/%s/tags" % (SERVER, RECIPE_ID)

    def test_index_all(self):
        query = requests.get(self.url)

        self.assertTrue(query.ok, msg=query.json())
        self.assertIsInstance(query.json().get('data'), list)


class TestTagAdd(TestCase):
    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        self.url = "%s/recipes/%s/tags/add" % (SERVER, RECIPE_ID)

    def test_add(self):
        params = {'name': LABEL_NAMES[1]}
        query = requests.post(self.url, data=params)

        self.assertTrue(query.ok, msg=query.json())

    def test_add_no_name(self):
        params = {}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_add_same(self):
        params = {'name': LABEL_NAMES[0]}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_add_wrong_field(self):
        params = {'ingredient': 'Nonexistsent'}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())

    def test_add_invalid_name(self):
        params = {'name': ''}
        query = requests.post(self.url, data=params)

        self.assertFalse(query.ok, msg=query.json())


class TestTagDelete(TestCase):
    @classmethod
    def setUpClass(cls):
        create_objects()

    @classmethod
    def tearDownClass(cls):
        delete_objects()

    def setUp(self):
        self.url = "%s/recipes/%s/tags" % (SERVER, RECIPE_ID)

    def test_delete(self):
        query = requests.delete("%s/%s" % (self.url, LABEL_IDS[0]))

        self.assertTrue(query.ok, msg=query.json())

    def test_delete_nonexistent(self):
        query = requests.delete("%s/%s" % (self.url, 'nonexistent'))

        self.assertFalse(query.ok, msg=query.json())
