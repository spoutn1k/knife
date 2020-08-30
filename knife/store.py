"""
store.py

Implementation of the Store class
"""

from flask import request
from knife import helpers
from knife.models import Dish, Label, Ingredient
from knife.exceptions import *


def validate_query(args_dict, authorized_keys):
    for key in list(args_dict.keys()):
        if key not in authorized_keys:
            raise InvalidQuery(key)


def format_output(func):
    """
    Decoration, encasing the output of the function into a dict for it to be sent via the api.
    Exceptions are caught and parsed to have a clear error message
    """
    def wrapper(*args, **kwargs):
        try:
            data = func(*args, **kwargs)
        except KnifeError as kerr:
            return {'accept': False, 'error': str(kerr), 'data': kerr.data}
        return {'accept': True, 'data': data}

    wrapper.__name__ = func.__name__
    return wrapper


class Store:
    """
    Class acting as the middleman between the api front and the database driver
    This abstracts the methods of the driver for them to be interchangeable
    """
    def __init__(self, driver):
        self.driver = driver

#  _                          _ _            _
# (_)_ __   __ _ _ __ ___  __| (_) ___ _ __ | |_
# | | '_ \ / _` | '__/ _ \/ _` | |/ _ \ '_ \| __|
# | | | | | (_| | | |  __/ (_| | |  __/ | | | |_
# |_|_| |_|\__, |_|  \___|\__,_|_|\___|_| |_|\__|
#          |___/

    @format_output
    def create_ingredient(self):
        """
        Create a ingredient object from the params in arguments
        """
        params = helpers.fix_args(dict(request.form))
        validate_query(params, ['name'])

        if 'name' not in params.keys():
            raise InvalidQuery(params)

        ingredient = Ingredient(params)
        stored = self.driver.ingredient_get(
            {'simple_name': ingredient.simple_name})

        if stored:
            raise IngredientAlreadyExists(stored[0])

        self.driver.ingredient_put(ingredient)
        return ingredient.serializable

    @format_output
    def ingredient_lookup(self):
        """
        Get an ingredient list, matching the parameters passed in args
        """
        args = helpers.fix_args(dict(request.args))
        validate_query(args, ['name', 'id'])
        stored = self.driver.ingredient_get(args, match=True)
        return [Ingredient(params).serializable for params in stored]

    @format_output
    def delete_ingredient(self, ingredient_id):
        """
        Delete an ingredient from an id
        """
        stored = self.driver.ingredient_get({'id': ingredient_id})
        if not stored:
            raise IngredientNotFound(ingredient_id)

        stored = self.driver.requirement_get({'ingredient_id': ingredient_id})
        if stored:
            raise IngredientInUse(len(stored))

        self.driver.ingredient_delete(ingredient_id)

    @format_output
    def edit_ingredient(self, ingredient_id):
        args = helpers.fix_args(dict(request.form))

        if not self.driver.ingredient_get({'id': ingredient_id}):
            raise IngredientNotFound(ingredient_id)

        validate_query(args, ['name'])
        if 'name' in args:
            args['simple_name'] = helpers.simplify(args['name'])

        self.driver.ingredient_update(ingredient_id, args)

    @format_output
    def merge_ingredient(self, dest_id):
        target_id = request.form['id']

        if not self.driver.ingredient_get({'id': dest_id}):
            raise IngredientNotFound(dest_id)
        if not self.driver.ingredient_get({'id': target_id}):
            raise IngredientNotFound(target_id)

        self.driver.requirement_update({'ingredient_id': target_id},
                                       {'ingredient_id': dest_id})

        self.delete_ingredient(target_id)

#      _ _     _
#   __| (_)___| |__
#  / _` | / __| '_ \
# | (_| | \__ \ | | |
#  \__,_|_|___/_| |_|

    @format_output
    def create_dish(self):
        """
        Create a dish object from the params in arguments
        """
        params = helpers.fix_args(dict(request.form))
        validate_query(params, ['name', 'author', 'directions'])
        if 'name' not in params.keys():
            raise InvalidQuery(params)

        dish = Dish(params)

        if self.driver.dish_get({'simple_name': dish.simple_name}):
            raise DishAlreadyExists(dish.name)

        self.driver.dish_put(dish)
        return dish.serializable

    @format_output
    def dish_lookup(self):
        """
        Get a dish list, matching the parameters passed in args
        """
        args = helpers.fix_args(dict(request.args))

        validate_query(args, ['name', 'id', 'author', 'directions'])
        if args.get('name'):
            args['simple_name'] = helpers.simplify(args.pop('name'))
        return self.driver.dish_lookup(args)

    @format_output
    def delete_dish(self, dish_id):
        """
        Delete a dish from an id
        """
        if not self.driver.dish_get({'id': dish_id}):
            raise DishNotFound(dish_id)
        self.driver.dish_delete(dish_id)

    @format_output
    def get_dish(self, dish_id):
        """
        Get full details about the dish of the specified id
        """
        results = self.driver.dish_get({'id': dish_id})
        if not results:
            raise DishNotFound(dish_id)
        dish_data = results[0]

        dish_data['requirements'] = self.show_requirements(dish_id).get(
            'data', [])
        dish_data['tags'] = self.driver.tag_get({'dish_id': dish_id})
        dish_data['dependencies'] = self.driver.dish_requires(dish_id)

        return Dish(dish_data).serializable

    @format_output
    def edit_dish(self, dish_id):
        args = helpers.fix_args(dict(request.form))
        if not self.driver.dish_get({'id': dish_id}):
            raise DishNotFound(dish_id)
        validate_query(args, ['name', 'author', 'directions'])
        if 'name' in args:
            args['simple_name'] = helpers.simplify(args['name'])
        self.driver.dish_update(dish_id, args)

    @format_output
    def get_tags(self, dish_id):
        if not self.driver.dish_get({'id': dish_id}):
            raise DishNotFound(dish_id)
        return self.driver.tag_get({'dish_id': dish_id})

    @format_output
    def tag_dish(self, dish_id):
        """
        Tag a dish with a label
        """
        args = helpers.fix_args(dict(request.form))

        if not self.driver.dish_get({'id': dish_id}):
            raise DishNotFound(dish_id)

        label = self.create_label(args).get('data')
        if self.driver.tag_get({
                'dish_id': dish_id,
                'label_id': label.get('id')
        }):
            raise TagAlreadyExists(dish_id, label.get('id'))

        self.driver.dish_tag(dish_id, label.get('id'))

    @format_output
    def untag_dish(self, dish_id, label_id):
        """
        Untag a dish with a label
        """
        if not self.driver.label_get({'id': label_id}):
            raise LabelNotFound(label_id)
        if not self.driver.tag_get({'dish_id': dish_id, 'label_id': label_id}):
            raise TagNotFound(dish_id, label_id)
        self.driver.dish_untag(dish_id, label_id)

    @format_output
    def get_deps(self, dish_id):
        if not self.driver.dish_get({'id': dish_id}):
            raise DishNotFound(dish_id)
        return self.driver.dish_requires(dish_id)

    @format_output
    def link_dish(self, dish_id):
        """
        Specify a recipe requirement for a recipe
        """
        required_id = request.form.get('required')

        if not self.driver.dish_get({'id': dish_id}):
            raise DishNotFound(dish_id)

        if not self.driver.dish_get({'id': required_id}):
            raise DishNotFound(required_id)

        self.driver.dish_link(dish_id, required_id)

    @format_output
    def unlink_dish(self, dish_id, required_id):
        """
        Delete a recipe requirement for a recipe
        """
        self.driver.dish_unlink(dish_id, required_id)

#                       _                               _
#  _ __ ___  __ _ _   _(_)_ __ ___ _ __ ___   ___ _ __ | |_
# | '__/ _ \/ _` | | | | | '__/ _ \ '_ ` _ \ / _ \ '_ \| __|
# | | |  __/ (_| | |_| | | | |  __/ | | | | |  __/ | | | |_
# |_|  \___|\__, |\__,_|_|_|  \___|_| |_| |_|\___|_| |_|\__|
#              |_|

    @format_output
    def show_requirements(self, dish_id):
        requirement_list = []
        for raw_data in self.driver.requirement_get({'dish_id': dish_id}):
            results = self.driver.ingredient_get(
                {'id': raw_data.get('ingredient_id')})
            req = {
                'ingredient': results[0],
                'quantity': raw_data.get('quantity')
            }
            requirement_list.append(req)

        return requirement_list

    @format_output
    def add_requirement(self, dish_id):
        """
        Add a requirement to a dish
        """

        ingredient_id = request.form.get('ingredient')
        quantity = request.form.get('quantity')

        if not ingredient_id or not quantity:
            raise InvalidQuery("Missing parameter")

        if not self.driver.dish_get({'id': dish_id}):
            raise DishNotFound(dish_id)

        ing_list = self.driver.ingredient_get({'id': ingredient_id})

        if not ing_list:
            raise IngredientNotFound(ingredient_id)

        if self.driver.requirement_exists({
                'dish_id': dish_id,
                'ingredient_id': ingredient_id
        }):
            raise RequirementAlreadyExists(dish_id, ingredient_id)

        self.driver.requirement_put({
            'dish_id': dish_id,
            'ingredient_id': ingredient_id,
            'quantity': quantity
        })

    @format_output
    def get_requirement(self, dish_id, ingredient_id):
        """
        Get a requirement from both the dish and the required ingredient
        """
        stored = self.driver.requirement_get({
            'dish_id': dish_id,
            'ingredient_id': ingredient_id
        })
        if not stored:
            raise RequirementNotFound(dish_id, ingredient_id)
        return stored[0]

    @format_output
    def edit_requirement(self, dish_id, ingredient_id):
        """
        Modify the quantity of a required ingredient
        """
        args = helpers.fix_args(dict(request.form))
        validate_query(args, ['quantity'])
        if not self.driver.requirement_get({
                'dish_id': dish_id,
                'ingredient_id': ingredient_id
        }):
            raise RequirementNotFound(dish_id, ingredient_id)
        self.driver.requirement_update(
            {
                'dish_id': dish_id,
                'ingredient_id': ingredient_id
            }, args)

    @format_output
    def delete_requirement(self, dish_id, ingredient_id):
        """
        Remove a requirement
        """
        if not self.driver.requirement_get({
                'dish_id': dish_id,
                'ingredient_id': ingredient_id
        }):
            raise RequirementNotFound(dish_id, ingredient_id)
        self.driver.requirement_delete({
            'dish_id': dish_id,
            'ingredient_id': ingredient_id
        })


#  _       _          _
# | | __ _| |__   ___| |
# | |/ _` | '_ \ / _ \ |
# | | (_| | |_) |  __/ |
# |_|\__,_|_.__/ \___|_|

    @format_output
    def label_lookup(self):
        """
        Get all labels which match the parameters in args
        """
        args = helpers.fix_args(dict(request.args))
        validate_query(args, ['name', 'id'])
        return self.driver.label_get(args, match=True)

    @format_output
    def delete_label(self, label_id):
        """
        Create a new label
        """
        if not self.driver.label_get({'id': label_id}):
            raise LabelNotFound(label_id)
        self.driver.label_delete(label_id)

    @format_output
    def create_label(self, args):
        validate_query(args, ['name'])
        label = Label(args)
        if label.name in ["", None] or " " in label.name:
            raise LabelInvalid(labelname)

        label_list = self.driver.label_get({'name': label.name})
        if label_list:
            raise LabelAlreadyExists(label_list[0])

        self.driver.label_put(label)
        return label.serializable

    @format_output
    def show_label(self, label_id):
        """
        Show dishes tagged with the label
        """
        if not self.driver.label_get({'id': label_id}):
            raise LabelNotFound(label_id)
        dish_list = self.driver.tag_show(label_id)
        return dish_list

    @format_output
    def edit_label(self, label_id):
        args = helpers.fix_args(dict(request.form))
        if not self.driver.label_get({'id': label_id}):
            raise LabelNotFound(label_id)
        validate_query(args, ['name'])
        if 'name' in args:
            args['simple_name'] = helpers.simplify(args['name'])
        self.driver.label_update(label_id, args)
