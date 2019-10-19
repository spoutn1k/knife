import json
import requests

class Connexion:
    def __init__(self, address):
        self.address = address

    def dish_list(self):
        try:
            query = requests.get("{}/dishes/".format(self.address))
        except requests.exceptions.ConnectionError:
            return ([], False, "Could not connect to server")

        if not query.ok:
            return ([], False, "HTTP request failed")

        return (query.json().get('dishes'), True, query.json().get('error'))

    def dish(self, hashid):
        return requests.get("{}/dishes/{}".format(self.address, hashid)).json()

    def create(self, name):
        try:
            query = requests.post("{}/dishes/new".format(self.address),
                data={'name': name, 'directions': ''})
        except requests.exceptions.ConnectionError:
            return ({}, False, "Could not connect to server")

        if not query.ok:
            return ({}, False, "HTTP request failed")

        return (query.json().get('dish'), True, query.json().get('error'))

    def save(self, dish_data):
        query = requests.post("{}/dishes/import".format(self.address),
                data={'json': json.dumps(dish_data)})

        if not query.ok:
            return (False, "HTTP request failed")

        return (query.json().get('accept'), query.json().get('dish'), query.json().get('error'))

    def delete(self, hashid):
        query = requests.get("{}/dishes/{}/delete".format(self.address, hashid))

        if not query.ok:
            return (False, "HTTP request failed")

        return (query.json().get('accept'), query.json().get('error'))

    def set_ingredient(self, dish, ingredient, quantity):
        return requests.post("{}/dishes/{}/ingredient".format(self.address, dish.get('id')),
                data={'ingredient': ingredient, 'quantity': quantity})

