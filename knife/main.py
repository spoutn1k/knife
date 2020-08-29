"""
api.py

Declaration of routes available in the knife app
"""

import os
from flask import Flask, request
from knife.store import Store
from knife.drivers import DRIVERS

APP = Flask(__name__)
BACK_END = Store(DRIVERS['sqlite'])

'''
Routes:
    GET             /ingredients
    POST            /ingredients/new
    PUT,DELETE      /ingredients/<ingredientid>
    PUT             /ingredients/<ingredientid>/merge

    GET             /dishes
    POST            /dishes/new
    GET,PUT,DELETE  /dishes/<dishid>

    GET             /dishes/<dishid>/requirements
    POST            /dishes/<dishid>/requirements/add
    PUT,DELETE      /dishes/<dishid>/requirements/<ingredientid>

    GET             /dishes/<dishid>/dependencies
    POST            /dishes/<dishid>/dependencies/add
    DELETE          /dishes/<dishid>/dependencies/<requiredid>

    GET             /dishes/<dishid>/tags
    POST            /dishes/<dishid>/tags/add
    DELETE          /dishes/<dishid>/tags/<labelid>

    GET             /labels
    GET,PUT,DELETE  /labels/<labelid>
'''


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


def delete_ingredient(ingredientid):
    """
    Delete the specified ingredient
    """
    return BACK_END.delete_ingredient(ingredientid)


def edit_ingredient(ingredientid):
    """
    Edit the specified ingredient
    """
    ingredient_data = fix_args(dict(request.form))
    return BACK_END.edit_ingredient(ingredientid, ingredient_data)


def merge_ingredient(ingredientid):
    """
    Merge the specified ingredients
    """
    target_id = request.form['id']
    return BACK_END.merge_ingredient(ingredientid, target_id)


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


def show_dish(dishid):
    """
    Show the dish of id `dishid`
    """
    return BACK_END.get_dish(dishid)


def edit_dish(dishid):
    """
    Show the dish of id `dishid`
    """
    dish_data = fix_args(dict(request.form))
    return BACK_END.edit_dish(dishid, dish_data)


def delete_dish(dishid):
    """
    Delete specified dish
    """
    return BACK_END.delete_dish(dishid)


def show_requirements(dishid):
    """
    Load a dish and show its requirements
    """
    return BACK_END.show_requirements(dishid)


def add_requirement(dishid):
    """
    Add a ingredient requirement to a dish
    """
    ingredientid = request.form.get('ingredient')
    quantity = request.form.get('quantity')
    return BACK_END.add_requirement(dishid, ingredientid, quantity)


def edit_requirement(dishid, ingredientid):
    """
    Modify an ingredient's required quantity
    """
    args = fix_args(dict(request.form))
    return BACK_END.edit_requirement(dishid, ingredientid, args)


def delete_requirement(dishid, ingredientid):
    """
    Delete a requirement
    """
    return BACK_END.delete_requirement(dishid, ingredientid)


def show_dependencies(dishid):
    """
    Show a dish's dependencies
    """
    return BACK_END.get_deps(dishid)


def add_dependency(dishid):
    """
    Add a pre-requisite to a dish
    """
    return BACK_END.link_dish(dishid, request.form.get('required'))


def delete_dependency(dishid, requiredid):
    """
    Delete a pre-requisite from a dish
    """
    return BACK_END.unlink_dish(dishid, requiredid)


def show_dish_tags(dishid):
    """
    List a recipe's tags
    """
    return BACK_END.get_tags(dishid)


def tag_dish(dishid):
    """
    Tag a dish with a label
    """
    args = fix_args(dict(request.form))
    return BACK_END.tag_dish(dishid, args)


def untag_dish(dishid, labelid):
    """
    Untag a dish with a label
    """
    return BACK_END.untag_dish(dishid, labelid)


def list_labels():
    """
    Return a list of all recorded labels
    """
    args = fix_args(dict(request.args))
    return BACK_END.label_lookup(args)


def show_label(labelid):
    """
    Show all the dishes tagged with a label
    """
    return BACK_END.show_label(labelid)


def edit_label(labelid):
    """
    Show all the dishes tagged with a label
    """
    args = fix_args(dict(request.form))
    return BACK_END.edit_label(labelid, args)


def delete_label(labelid):
    """
    Delete a label and all associated tags
    """
    return BACK_END.delete_label(labelid)


ROUTES = (
    ('/ingredients', list_ingredients, ['GET']),
    ('/ingredients/new', create_ingredient, ['POST']),
    ('/ingredients/<ingredientid>', edit_ingredient, ['PUT']),
    ('/ingredients/<ingredientid>', delete_ingredient, ['DELETE']),
    ('/dishes', list_dishes, ['GET']),
    ('/dishes/new', create_dish, ['POST']),
    ('/dishes/<dishid>', show_dish, ['GET']),
    ('/dishes/<dishid>', edit_dish, ['PUT']),
    ('/dishes/<dishid>', delete_dish, ['DELETE']),
    ('/dishes/<dishid>/requirements', show_requirements, ['GET']),
    ('/dishes/<dishid>/requirements/add', add_requirement, ['POST']),
    ('/dishes/<dishid>/requirements/<ingredientid>', edit_requirement, ['PUT'
                                                                        ]),
    ('/dishes/<dishid>/requirements/<ingredientid>', delete_requirement,
     ['DELETE']),
    ('/dishes/<dishid>/dependencies', show_dependencies, ['GET']),
    ('/dishes/<dishid>/dependencies/add', add_dependency, ['POST']),
    ('/dishes/<dishid>/dependencies/<requiredid>', delete_dependency,
     ['DELETE']),
    ('/dishes/<dishid>/tags', show_dish_tags, ['GET']),
    ('/dishes/<dishid>/tags/add', tag_dish, ['POST']),
    ('/dishes/<dishid>/tags/<labelname>', untag_dish, ['DELETE']),
    ('/labels', list_labels, ['GET']),
    ('/labels/<labelid>', show_label, ['GET']),
    ('/labels/<labelid>', edit_label, ['PUT']),
    ('/labels/<labelid>', delete_label, ['DELETE']),
)

for rule, view_func, methods in ROUTES:
    APP.add_url_rule(rule=rule,
                     endpoint=view_func.__name__,
                     view_func=view_func,
                     methods=methods)

if __name__ == '__main__':
    APP.run()
