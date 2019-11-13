"""
api.py

Declaration of routes available in the knife app
"""

import json
from flask import Flask, request
from store import Store
from drivers import sqlite
from exceptions import *

APP = Flask(__name__)
BACK_END = Store(sqlite)

'''
Routes:
    GET             /ingredients
    POST            /ingredients/new
    DELETE          /ingredients/<ingredientid>

    GET             /dishes
    POST            /dishes/new
    GET,DELETE      /dishes/<dishid>

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
    GET,DELETE      /labels/<labelid>
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
    try:
        results = BACK_END.ingredient_lookup(args)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    data = [{'id': ingredient.id, 'name': ingredient.name} for ingredient in results]
    return {'accept': True, 'data': data}

@APP.route('/ingredients/new', methods=['POST'])
def create_ingredient():
    """
    Create a new ingredient from the data in the `json` field of the query
    """
    try:
        ing_data = json.loads(request.form['json'])
    except json.decoder.JSONDecodeError:
        return {'accept': False, 'error': 'Invalid json syntax'}

    ingredient = BACK_END.create_ingredient(ing_data)
    try:
        ingredient.save()
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True, 'data': ingredient.serializable}

@APP.route('/ingredients/<ingredientid>', methods=['DELETE'])
def delete_ingredient(ingredientid):
    """
    Delete the specified ingredient
    """
    try:
        ingredient = BACK_END.delete_ingredient(ingredientid)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True, 'data': ingredient}

@APP.route('/dishes', methods=['GET'])
def list_dishes():
    """
    List dishes recorded in the app
    Search is supported by passing GET arguments to the query
    """
    args = fix_args(dict(request.args))
    try:
        results = BACK_END.dish_lookup(args)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    dishes = [{'id': dish.id, 'name': dish.name} for dish in results]
    return {'accept': True, 'data': dishes}

@APP.route('/dishes/new', methods=['POST'])
def create_dish():
    """
    Create dish from data passed in the `json` field of the query
    """
    try:
        dish_data = json.loads(request.form['json'])
    except json.decoder.JSONDecodeError:
        return {'accept': False, 'error': 'Invalid json syntax'}

    dish = BACK_END.create_dish(dish_data)
    try:
        dish.save()
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True, 'data': dish.serializable}

@APP.route('/dishes/<dishid>', methods=['GET'])
def show_dish(dishid):
    """
    Show the dish of id `dishid`
    """
    try:
        dish = BACK_END.get_dish(dishid)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True, 'data': dish}

@APP.route('/dishes/<dishid>', methods=['DELETE'])
def delete_dish(dishid):
    """
    Delete specified dish
    """
    try:
        dish = BACK_END.delete_dish(dishid)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True, 'data': dish}

@APP.route('/dishes/<dishid>/requirements', methods=['GET'])
def show_requirements(dishid):
    """
    Load a dish and show its requirements
    """
    try:
        dish = BACK_END.get_dish(dishid)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    data = dish.get('requirements') if dish else None
    return {'accept': True, 'data': data}

@APP.route('/dishes/<dishid>/requirements/add', methods=['POST'])
def add_requirement(dishid):
    """
    Add a ingredient requirement to a dish
    """
    ingredientid = request.form.get('ingredient')
    quantity = request.form.get('quantity')
    try:
        BACK_END.add_requirement(dishid, ingredientid, quantity)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True}

@APP.route('/dishes/<dishid>/requirements/<ingredientid>', methods=['PUT'])
def edit_requirement(dishid, ingredientid):
    """
    Modify an ingredient's required quantity
    """
    try:
        BACK_END.edit_requirement(dishid, ingredientid, request.form.get('quantity'))
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True}

@APP.route('/dishes/<dishid>/requirements/<ingredientid>', methods=['DELETE'])
def delete_requirement(dishid, ingredientid):
    """
    Delete a requirement
    """
    try:
        BACK_END.delete_requirement(dishid, ingredientid)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True}

@APP.route('/dishes/<dishid>/dependencies', methods=['GET'])
def show_dependencies(dishid):
    """
    Show a dish's dependencies
    """
    try:
        dish = BACK_END.get_dish(dishid)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    data = dish.get('dependencies') if dish else None
    return {'accept': True, 'data': data}

@APP.route('/dishes/<dishid>/dependencies/add', methods=['POST'])
def add_dependency(dishid):
    """
    Add a pre-requisite to a dish
    """
    try:
        BACK_END.link_dish(dishid, request.form.get('required'))
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True}

@APP.route('/dishes/<dishid>/dependencies/<requiredid>', methods=['DELETE'])
def delete_dependency(dishid, requiredid):
    """
    Delete a pre-requisite from a dish
    """
    try:
        BACK_END.unlink_dish(dishid, requiredid)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True}

@APP.route('/dishes/<dishid>/tags', methods=['GET'])
def show_dish_tags(dishid):
    """
    List a recipe's tags
    """
    try:
        dish = BACK_END.get_dish(dishid)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    data = dish.get('tags') if dish else None
    return {'accept': True, 'data': data}

@APP.route('/dishes/<dishid>/tags/add', methods=['POST'])
def tag_dish(dishid):
    """
    Tag a dish with a label
    """
    tagname = request.form.get('name')
    try:
        BACK_END.tag_dish(dishid, tagname)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True}

@APP.route('/dishes/<dishid>/tags/<labelid>', methods=['DELETE'])
def untag_dish(dishid, labelid):
    """
    Untag a dish with a label
    """
    try:
        BACK_END.untag_dish(dishid, labelid)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True}

@APP.route('/labels', methods=['GET'])
def list_labels():
    """
    Return a list of all recorded labels
    """
    args = fix_args(dict(request.args))
    try:
        data = BACK_END.label_lookup(args)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True, 'data': data}

@APP.route('/labels/<labelid>', methods=['GET'])
def show_label(labelid):
    """
    Show all the dishes tagged with a label
    """
    try:
        dishes = BACK_END.show_label(labelid)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True, 'data': dishes}

@APP.route('/labels/<labelid>', methods=['DELETE'])
def delete_label(labelid):
    """
    Delete a label and all associated tags
    """
    try:
        BACK_END.delete_label(labelid)
    except KnifeError as kerr:
        return {'accept': False, 'error': str(kerr)}
    return {'accept': True}

if __name__ == '__main__':
    APP.run()
