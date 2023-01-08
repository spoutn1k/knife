import os
import sys
import unittest

try:
    SERVER = f"http://{os.environ['KNIFE_SERVER']}:{os.environ['KNIFE_PORT']}"
except KeyError:
    print("KNIFE_SERVER is not set. Aborting.", file=sys.stderr)
    exit(1)


def show_url(func):

    def wrap(*args, **kwargs):
        self = func.__self__

        message = "url: %s" % self.url

        if kwargs.get('msg'):
            message = "%s, %s" % (message, kwargs.get('msg'))

        kwargs.update({'msg': message})

        return func(*args, **kwargs)

    wrap.__name__ = func.__name__
    return wrap


class TestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestCase, self).__init__(*args, **kwargs)

        self.url = "NOTSET"
        self.assertEqual = show_url(self.assertEqual)
        self.assertTrue = show_url(self.assertTrue)
        self.assertFalse = show_url(self.assertFalse)
        #self.assertIsInstance = show_url(self.assertIsInstance)


from test.test_recipes import TestRecipeIndex, TestRecipeCreate, TestRecipeDelete, TestRecipeEdit, TestRecipeShow
from test.test_ingredients import TestIngredientIndex, TestIngredientCreate, TestIngredientDelete, TestIngredientEdit
from test.test_labels import TestLabelIndex, TestLabelCreate, TestLabelDelete, TestLabelEdit
from test.test_requirements import TestRequirementShow, TestRequirementAdd, TestRequirementDelete, TestRequirementEdit
from test.test_tags import TestTagShow, TestTagAdd, TestTagDelete
from test.test_dependencies import TestDependencyShow, TestDependencyAdd, TestDependencyDelete
