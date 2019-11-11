from flask import Flask, request
from store import store
from drivers import sqlite
import json

app = Flask(__name__)
back_end = store(sqlite)

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

    GET     /labels
    GET     /labels/<tagname>
'''

@app.route('/dishes', methods=['GET'])
def list_dishes():
    return {'accept': True,
            'dishes': [{'id': dish.id,
                'name': dish.name} for dish in back_end.dish_lookup(dict(request.args))],
            'error': None}

@app.route('/dishes/new', methods=['POST'])
def create_dish():
    dish = back_end.create(json.loads(request.form['json']))
    valid, error = dish.save()
    return {'accept': valid, 'dish': dish.json, 'error': error}

@app.route('/dishes/<dishid>', methods=['GET'])
def show_dish(dishid):
    valid, dish, error = back_end.get_dish(dishid)
    return {'accept': valid, 'dish': dish, 'error': error}

@app.route('/dishes/<dishid>', methods=['DELETE'])
def delete_dish(dishid):
    valid, dish, error = back_end.delete(dishid)
    return {'accept': valid, 'dish': dish, 'error': error}

@app.route('/dishes/<dishid>/ingredients', methods=['GET'])
def show_requirements(dishid):
    status, dish, error = back_end.get_dish(dishid)
    data = dish.get('ingredients') if dish else None
    return {'accept': status, 'data': data, 'error': error}

@app.route('/dishes/<dishid>/ingredients/add', methods=['POST'])
def add_requirement(dishid):
    valid, requirement, error = back_end.add_requirement(dishid, request.form.get('ingredient'), request.form.get('quantity'))
    return {'accept': valid, 'data': requirement, 'error': error}

@app.route('/dishes/<dishid>/ingredients/<ingredientid>', methods=['PUT'])
def edit_requirement(dishid, ingredientid):
    status, error = back_end.edit_requirement(dishid, ingredientid, request.form.get('quantity'))
    return {'accept': status, 'data': None, 'error': error}

@app.route('/dishes/<dishid>/ingredients/<ingredientid>', methods=['DELETE'])
def delete_requirement(dishid, ingredientid):
    status, requirement, error = back_end.delete_requirement(dishid, ingredientid)
    return {'accept': status, 'data': requirement, 'error': error}

@app.route('/dishes/<dishid>/tags', methods=['GET'])
def show_dish_tags(dishid):
    valid, dish, error = back_end.get_dish(dishid)
    return {'accept': valid, 'labels': dish.get('tags'), 'error': error}

@app.route('/dishes/<dishid>/tags/add', methods=['POST'])
def tag(dishid):
    tagname = request.form.get('name')
    status, error = back_end.tag_dish(dishid, tagname)
    return {'accept': status, 'error': error}

@app.route('/ingredients', methods=['GET'])
def list_ingredients():
    return {'ingredients': [{'id': ingredient.id,
                             'name': ingredient.name} for ingredient in back_end.ingredient_lookup(dict(request.args))]}

@app.route('/ingredients/add', methods=['POST'])
def create_ingredient():
    ingredient = back_end.create_ingredient(json.loads(request.form['json']))
    valid, error = ingredient.save()
    return {'accept': valid, 'dish': ingredient.json, 'error': error}

@app.route('/ingredients/<ingredientid>', methods=['DELETE'])
def delete_ingredient(ingredientid):
    status, ingredient, error = back_end.delete_ingredient(ingredientid)
    return {'accept': status, 'data': ingredient, 'error': error}

@app.route('/labels', methods=['GET'])
def show_labels():
    stub = request.args.get('name', "")
    return {'labels': back_end.labels(stub)}

@app.route('/labels/<tagname>', methods=['GET'])
def show_label(tagname):
    status, dishes, error = back_end.show_label(tagname)
    return {'accept': status, 'dishes': dishes, 'error': error}

if __name__ == '__main__':
    app.run()
