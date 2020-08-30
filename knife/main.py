"""
api.py

Declaration of routes available in the knife app
"""

import os
from flask import Flask, request
from knife.store import Store
from knife.drivers import DRIVERS

APP = Flask(__name__)
BACK_END = Store(DRIVERS['pgsql'])


def fix_args(dictionnary):
    """
    This code exists because python changed the way it translated dictionnaries between versions
    When request.args was processed to be used later in the code, lists were created in 3.5 and
    not in 3.7.
    This function fixes that by parsing the dictionnary first
    """
    for (key, value) in dictionnary.items():
        if isinstance(value, list):
            dictionnary[key] = value[0]
    return dictionnary


def list_ingredients():
    """
    List ingredients recorded in the app
    Search is supported by passing GET arguments to the query
    """
    args = fix_args(dict(request.args))
    return BACK_END.ingredient_lookup(args)


def create_ingredient():
    """
    Create a new ingredient from the form passed in the request
    """
    ingredient_data = fix_args(dict(request.form))
    return BACK_END.create_ingredient(ingredient_data)


def edit_ingredient(ingredient_id):
    """
    Edit the specified ingredient
    """
    ingredient_data = fix_args(dict(request.form))
    return BACK_END.edit_ingredient(ingredient_id, ingredient_data)


def merge_ingredient(ingredient_id):
    """
    Merge the specified ingredients
    """
    target_id = request.form['id']
    return BACK_END.merge_ingredient(ingredient_id, target_id)


def list_dishes():
    """
    List dishes recorded in the app
    Search is supported by passing GET arguments to the query
    """
    args = fix_args(dict(request.args))
    return BACK_END.dish_lookup(args)


def create_dish():
    """
    Create dish from data passed in the form
    """
    dish_data = fix_args(dict(request.form))
    return BACK_END.create_dish(dish_data)


def edit_dish(dish_id):
    """
    Show the dish of id `dish_id`
    """
    dish_data = fix_args(dict(request.form))
    return BACK_END.edit_dish(dish_id, dish_data)


def add_requirement(dish_id):
    """
    Add a ingredient requirement to a dish
    """
    ingredient_id = request.form.get('ingredient')
    quantity = request.form.get('quantity')
    return BACK_END.add_requirement(dish_id, ingredient_id, quantity)


def edit_requirement(dish_id, ingredient_id):
    """
    Modify an ingredient's required quantity
    """
    args = fix_args(dict(request.form))
    return BACK_END.edit_requirement(dish_id, ingredient_id, args)


def add_dependency(dish_id):
    """
    Add a pre-requisite to a dish
    """
    return BACK_END.link_dish(dish_id, request.form.get('required'))


def tag_dish(dish_id):
    """
    Tag a dish with a label
    """
    args = fix_args(dict(request.form))
    return BACK_END.tag_dish(dish_id, args)


def list_labels():
    """
    Return a list of all recorded labels
    """
    args = fix_args(dict(request.args))
    return BACK_END.label_lookup(args)


def edit_label(label_id):
    """
    Show all the dishes tagged with a label
    """
    args = fix_args(dict(request.form))
    return BACK_END.edit_label(label_id, args)


ROUTES = (
    (['GET'], list_ingredients, '/ingredients'),
    (['POST'], create_ingredient, '/ingredients/new'),
    (['PUT'], edit_ingredient, '/ingredients/<ingredient_id>'),
    (['DELETE'], BACK_END.delete_ingredient, '/ingredients/<ingredient_id>'),
    (['GET'], list_dishes, '/dishes'),
    (['POST'], create_dish, '/dishes/new'),
    (['GET'], BACK_END.get_dish, '/dishes/<dish_id>'),
    (['PUT'], edit_dish, '/dishes/<dish_id>'),
    (['DELETE'], BACK_END.delete_dish, '/dishes/<dish_id>'),
    (['GET'], BACK_END.show_requirements, '/dishes/<dish_id>/requirements'),
    (['POST'], add_requirement, '/dishes/<dish_id>/requirements/add'),
    (['PUT'], edit_requirement,
     '/dishes/<dish_id>/requirements/<ingredient_id>'),
    (['DELETE'], BACK_END.delete_requirement,
     '/dishes/<dish_id>/requirements/<ingredient_id>'),
    (['GET'], BACK_END.get_deps, '/dishes/<dish_id>/dependencies'),
    (['POST'], add_dependency, '/dishes/<dish_id>/dependencies/add'),
    (['DELETE'], BACK_END.unlink_dish,
     '/dishes/<dish_id>/dependencies/<required_id>'),
    (['GET'], BACK_END.get_tags, '/dishes/<dish_id>/tags'),
    (['POST'], tag_dish, '/dishes/<dish_id>/tags/add'),
    (['DELETE'], BACK_END.untag_dish, '/dishes/<dish_id>/tags/<label_id>'),
    (['GET'], list_labels, '/labels'),
    (['GET'], BACK_END.show_label, '/labels/<label_id>'),
    (['PUT'], edit_label, '/labels/<label_id>'),
    (['DELETE'], BACK_END.delete_label, '/labels/<label_id>'),
)

for methods, view_func, rule in ROUTES:
    APP.add_url_rule(rule=rule,
                     endpoint=view_func.__name__,
                     view_func=view_func,
                     methods=methods)

if __name__ == '__main__':
    APP.run()
