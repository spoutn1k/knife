"""
api.py

Declaration of routes available in the knife app
"""

import os
from flask import Flask, request
from store import Store
from drivers import sqlite, pgsql

APP = Flask(__name__)
BACK_END = Store(pgsql)

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

@APP.route('/ingredients', methods=['GET'])
def list_ingredients():
    """
    List ingredients recorded in the app
    Search is supported by passing GET arguments to the query
    """
    args = fix_args(dict(request.args))
    return BACK_END.ingredient_lookup(args)

@APP.route('/ingredients/new', methods=['POST'])
def create_ingredient():
    """
    Create a new ingredient from the form passed in the request
    """
    ingredient_data = fix_args(dict(request.form))
    return BACK_END.create_ingredient(ingredient_data)

@APP.route('/ingredients/<ingredientid>', methods=['DELETE'])
def delete_ingredient(ingredientid):
    """
    Delete the specified ingredient
    """
    return BACK_END.delete_ingredient(ingredientid)

@APP.route('/ingredients/<ingredientid>', methods=['PUT'])
def edit_ingredient(ingredientid):
    """
    Edit the specified ingredient
    """
    ingredient_data = fix_args(dict(request.form))
    return BACK_END.edit_ingredient(ingredientid, ingredient_data)

@APP.route('/ingredients/<ingredientid>/merge', methods=['PUT'])
def merge_ingredient(ingredientid):
    """
    Merge the specified ingredients
    """
    target_id = request.form['id']
    return BACK_END.merge_ingredient(ingredientid, target_id)

@APP.route('/dishes', methods=['GET'])
def list_dishes():
    """
    List dishes recorded in the app
    Search is supported by passing GET arguments to the query
    """
    args = fix_args(dict(request.args))
    return BACK_END.dish_lookup(args)

@APP.route('/dishes/new', methods=['POST'])
def create_dish():
    """
    Create dish from data passed in the form
    """
    dish_data = fix_args(dict(request.form))
    return BACK_END.create_dish(dish_data)

@APP.route('/dishes/<dishid>', methods=['GET'])
def show_dish(dishid):
    """
    Show the dish of id `dishid`
    """
    return BACK_END.get_dish(dishid)

@APP.route('/dishes/<dishid>', methods=['PUT'])
def edit_dish(dishid):
    """
    Show the dish of id `dishid`
    """
    dish_data = fix_args(dict(request.form))
    return BACK_END.edit_dish(dishid, dish_data)

@APP.route('/dishes/<dishid>', methods=['DELETE'])
def delete_dish(dishid):
    """
    Delete specified dish
    """
    return BACK_END.delete_dish(dishid)

@APP.route('/dishes/<dishid>/requirements', methods=['GET'])
def show_requirements(dishid):
    """
    Load a dish and show its requirements
    """
    return BACK_END.show_requirements(dishid)

@APP.route('/dishes/<dishid>/requirements/add', methods=['POST'])
def add_requirement(dishid):
    """
    Add a ingredient requirement to a dish
    """
    ingredientid = request.form.get('ingredient')
    quantity = request.form.get('quantity')
    return BACK_END.add_requirement(dishid, ingredientid, quantity)

@APP.route('/dishes/<dishid>/requirements/<ingredientid>', methods=['PUT'])
def edit_requirement(dishid, ingredientid):
    """
    Modify an ingredient's required quantity
    """
    args = fix_args(dict(request.form))
    return BACK_END.edit_requirement(dishid, ingredientid, args)

@APP.route('/dishes/<dishid>/requirements/<ingredientid>', methods=['DELETE'])
def delete_requirement(dishid, ingredientid):
    """
    Delete a requirement
    """
    return BACK_END.delete_requirement(dishid, ingredientid)

@APP.route('/dishes/<dishid>/dependencies', methods=['GET'])
def show_dependencies(dishid):
    """
    Show a dish's dependencies
    """
    return BACK_END.get_deps(dishid)

@APP.route('/dishes/<dishid>/dependencies/add', methods=['POST'])
def add_dependency(dishid):
    """
    Add a pre-requisite to a dish
    """
    return BACK_END.link_dish(dishid, request.form.get('required'))

@APP.route('/dishes/<dishid>/dependencies/<requiredid>', methods=['DELETE'])
def delete_dependency(dishid, requiredid):
    """
    Delete a pre-requisite from a dish
    """
    return BACK_END.unlink_dish(dishid, requiredid)

@APP.route('/dishes/<dishid>/tags', methods=['GET'])
def show_dish_tags(dishid):
    """
    List a recipe's tags
    """
    return BACK_END.get_tags(dishid)

@APP.route('/dishes/<dishid>/tags/add', methods=['POST'])
def tag_dish(dishid):
    """
    Tag a dish with a label
    """
    args = fix_args(dict(request.form))
    return BACK_END.tag_dish(dishid, args)

@APP.route('/dishes/<dishid>/tags/<labelid>', methods=['DELETE'])
def untag_dish(dishid, labelid):
    """
    Untag a dish with a label
    """
    return BACK_END.untag_dish(dishid, labelid)

@APP.route('/labels', methods=['GET'])
def list_labels():
    """
    Return a list of all recorded labels
    """
    args = fix_args(dict(request.args))
    return BACK_END.label_lookup(args)

@APP.route('/labels/<labelid>', methods=['GET'])
def show_label(labelid):
    """
    Show all the dishes tagged with a label
    """
    return BACK_END.show_label(labelid)

@APP.route('/labels/<labelid>', methods=['PUT'])
def edit_label(labelid):
    """
    Show all the dishes tagged with a label
    """
    args = fix_args(dict(request.form))
    return BACK_END.edit_label(labelid, args)

@APP.route('/labels/<labelid>', methods=['DELETE'])
def delete_label(labelid):
    """
    Delete a label and all associated tags
    """
    return BACK_END.delete_label(labelid)

if __name__ == '__main__':
    APP.run()
