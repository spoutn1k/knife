from flask import Flask
from flask import request
from store import store
from drivers import sqlite
import json
app = Flask(__name__)

back_end = store(sqlite)

@app.route('/dishes/')
def dishes():
    return {'dishes': [{'id': dish.id, 'name': dish.name} for dish in back_end.dishes]}

@app.route('/dishes/<hashid>')
def show_dish(hashid):
    query = back_end.load({'id': hashid})

    if len(query) != 1:
        return {'accept': False}
    return query[0].params

@app.route('/dishes/<hashid>/delete')
def delete_dish(hashid):
    return {'accept': back_end.delete({'id': hashid})}

@app.route('/dishes/<hashid>/ingredient', methods=['POST'])
def add_ingredient(hashid):
    valid = back_end.add({'dish': hashid,
                    'ingredient': request.form['ingredient'],
                    'quantity': request.form['quantity']})
    return {'accept': valid}

@app.route('/dishes/new', methods=['POST'])
def create_dish():
    valid = back_end.create({'name': request.form['name'],
                             'author': request.form.get('author'),
                             'directions': request.form['directions']}).save()
    return {'accept': valid}

@app.route('/ingredients/')
def ingredients():
    return {'ingredients': [{'id': ingredient.id, 'name': ingredient.name} for ingredient in back_end.ingredients]}

if __name__ == '__main__':
    app.run(host='192.168.1.15')
