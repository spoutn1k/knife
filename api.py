from flask import Flask
from flask import request
from store import store
from drivers import sqlite
import json

app = Flask(__name__)
back_end = store(sqlite)

@app.route('/dishes', methods=['GET'])
def list_dishes():
    query = {}
    if request.args.get('name'):
        query['name'] = request.args.get('name')
    return {'accept': True,
            'dishes': [{'id': dish.id,
                'name': dish.name} for dish in back_end.dish_lookup(query)],
            'error': None}

@app.route('/dishes/new', methods=['POST'])
def create_dish():
    dish = back_end.create({'name': request.form['name'],
                             'author': request.form.get('author'),
                             'directions': request.form['directions']})
    valid, error = dish.save()
    return {'accept': valid, 'dish': dish.json, 'error': error}

@app.route('/dishes/<hashid>', methods=['GET'])
def show_dish(hashid):
    valid, dish, error = back_end.load_one({'id': hashid})
    return {'accept': valid, 'dish': dish.json, 'error': error}

@app.route('/dishes/<hashid>', methods=['DELETE'])
def delete_dish(hashid):
    valid = back_end.delete({'id': hashid})
    return {'accept': valid}

@app.route('/dishes/import', methods=['POST'])
def import_dish():
    dish = back_end.create(json.loads(request.form['json']))
    valid, error = dish.save()
    return {'accept': valid, 'dish': dish.json, 'error': error}

@app.route('/ingredients', methods=['GET'])
def list_ingredients():
    return {'ingredients': [{'id': ingredient.id,
                             'name': ingredient.name} for ingredient in back_end.ingredients]}

@app.route('/dishes/<hashid>/ingredient', methods=['POST'])
def add_ingredient(hashid):
    valid = back_end.add({'dish': hashid,
                    'ingredient': request.form['ingredient'],
                    'quantity': request.form['quantity']})
    return {'accept': valid}

if __name__ == '__main__':
    app.run()
