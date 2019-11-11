"""
api.py

Declaration of routes available in the knife app
"""

import json
from flask import Flask, request
from store import Store
from drivers import sqlite

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

    GET             /dishes/<dishid>/ingredients
    POST            /dishes/<dishid>/ingredients/add
    PUT,DELETE      /dishes/<dishid>/ingredients/<ingredientid>

    GET             /dishes/<dishid>/tags
    POST            /dishes/<dishid>/tags/add
    DELETE          /dishes/<dishid>/tags/<tagid>

    GET             /labels
    GET             /labels/<tagname>
'''

@APP.route('/ingredients', methods=['GET'])
def list_ingredients():
    """
    List ingredients recorded in the app
    Search is supported by passing GET arguments to the query
    """
    status, results, error = BACK_END.ingredient_lookup(dict(request.args))
    data = [{'id': ingredient.id, 'name': ingredient.name} for ingredient in results]
    return {'accept': status, 'data': data, 'error': error}

@APP.route('/ingredients/new', methods=['POST'])
def create_ingredient():
    """
    Create a new ingredient from the data in the `json` field of the query
    """
    try:
        ing_data = json.loads(request.form['json'])
    except json.decoder.JSONDecodeError:
        return {'accept': False, 'data': None, 'error': 'Invalid json syntax'}

    ingredient = BACK_END.create_ingredient(ing_data)
    valid, error = ingredient.save()
    return {'accept': valid, 'data': ingredient.serializable, 'error': error}

@APP.route('/ingredients/<ingredientid>', methods=['DELETE'])
def delete_ingredient(ingredientid):
    """
    Delete the specified ingredient
    """
    status, ingredient, error = BACK_END.delete_ingredient(ingredientid)
    return {'accept': status, 'data': ingredient, 'error': error}

@APP.route('/dishes', methods=['GET'])
def list_dishes():
    """
    List dishes recorded in the app
    Search is supported by passing GET arguments to the query
    """
    status, results, error = BACK_END.dish_lookup(dict(request.args))
    dishes = [{'id': dish.id, 'name': dish.name} for dish in results]
    return {'accept': status, 'data': dishes, 'error': error}

@APP.route('/dishes/new', methods=['POST'])
def create_dish():
    """
    Create dish from data passed in the `json` field of the query
    """
    try:
        dish_data = json.loads(request.form['json'])
    except json.decoder.JSONDecodeError:
        return {'accept': False, 'data': None, 'error': 'Invalid json syntax'}

    dish = BACK_END.create_dish(dish_data)
    valid, error = dish.save()
    return {'accept': valid, 'data': dish.serializable, 'error': error}

@APP.route('/dishes/<dishid>', methods=['GET'])
def show_dish(dishid):
    """
    Show the dish of id `dishid`
    """
    valid, dish, error = BACK_END.get_dish(dishid)
    return {'accept': valid, 'data': dish, 'error': error}

@APP.route('/dishes/<dishid>', methods=['DELETE'])
def delete_dish(dishid):
    """
    Delete specified dish
    """
    valid, dish, error = BACK_END.delete_dish(dishid)
    return {'accept': valid, 'data': dish, 'error': error}

@APP.route('/dishes/<dishid>/ingredients', methods=['GET'])
def show_requirements(dishid):
    """
    Load a dish and show its requirements
    """
    status, dish, error = BACK_END.get_dish(dishid)
    data = dish.get('requirements') if dish else None
    return {'accept': status, 'data': data, 'error': error}

@APP.route('/dishes/<dishid>/ingredients/add', methods=['POST'])
def add_requirement(dishid):
    """
    Add a ingredient requirement to a dish
    """
    ingredientid = request.form.get('ingredient')
    quantity = request.form.get('quantity')
    valid, requirement, error = BACK_END.add_requirement(dishid, ingredientid, quantity)
    return {'accept': valid, 'data': requirement, 'error': error}

@APP.route('/dishes/<dishid>/ingredients/<ingredientid>', methods=['PUT'])
def edit_requirement(dishid, ingredientid):
    """
    Modify an ingredient's required quantity
    """
    status, error = BACK_END.edit_requirement(dishid, ingredientid, request.form.get('quantity'))
    return {'accept': status, 'data': None, 'error': error}

@APP.route('/dishes/<dishid>/ingredients/<ingredientid>', methods=['DELETE'])
def delete_requirement(dishid, ingredientid):
    """
    Delete a requirement
    """
    status, requirement, error = BACK_END.delete_requirement(dishid, ingredientid)
    return {'accept': status, 'data': requirement, 'error': error}

@APP.route('/dishes/<dishid>/tags', methods=['GET'])
def show_dish_tags(dishid):
    """
    List a recipe's tags
    """
    status, dish, error = BACK_END.get_dish(dishid)
    data = dish.get('tags') if dish else None
    return {'accept': status, 'data': data, 'error': error}

@APP.route('/dishes/<dishid>/tags/add', methods=['POST'])
def tag(dishid):
    """
    Tag a dish with a label
    """
    tagname = request.form.get('name')
    status, error = BACK_END.tag_dish(dishid, tagname)
    return {'accept': status, 'error': error}

@APP.route('/labels', methods=['GET'])
def show_labels():
    """
    Return a list of all recorded labels
    """
    stub = request.args.get('name', "")
    status, data, error = BACK_END.labels(stub)
    return {'accept': status, 'data': data, 'error': error}

@APP.route('/labels/<tagname>', methods=['GET'])
def show_label(tagname):
    """
    Show all the dishes tagged with a label
    """
    status, dishes, error = BACK_END.show_label(tagname)
    return {'accept': status, 'data': dishes, 'error': error}

if __name__ == '__main__':
    APP.run()
