from flask import Flask
from flask import request
from store import store
from drivers import sqlite
import json
app = Flask(__name__)

back_end = store(sqlite)

@app.route('/dishes/')
def list_dishes():
    return {'dishes': [{'id': dish.id,
                        'name': dish.name} for dish in back_end.dishes]}

@app.route('/dishes/<hashid>')
def show_dish(hashid):
    dish = back_end.load_one({'id': hashid})

    if not dish:
        return {'accept': False}

    return dish.json

@app.route('/dishes/new', methods=['POST'])
def create_dish():
    valid = back_end.create({'name': request.form['name'],
                             'author': request.form.get('author'),
                             'directions': request.form['directions']}).save()
    return {'accept': valid}

@app.route('/dishes/<hashid>/delete')
def delete_dish(hashid):
    valid = back_end.delete({'id': hashid})
    return {'accept': valid}

@app.route('/dishes/import', methods=['POST'])
def import_dish():
    valid = back_end.create(json.loads(request.form['json'])).save()
    return {'accept': valid}

@app.route('/ingredients/')
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
