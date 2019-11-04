import json
import requests

def _wrapper(func):
    def call(*args, **kwargs):
        field = kwargs.pop('field')
        try:
            query = func(*args, **kwargs)
        except requests.exceptions.ConnectionError:
            return (None, False, "Could not connect to server")
        if not query.ok:
            return (None, False, "HTTP request failed ({})".format(query.status_code))
        data = query.json()
        return (data.get(field), data.get('accept'), data.get('error'))
    return call

get = _wrapper(requests.get)
post = _wrapper(requests.post)
delete = _wrapper(requests.delete)

class Connexion:
    def __init__(self, address):
        self.address = address

    def dish_list(self, pattern=""):
        if pattern != "":
            args = "?simple_name={}".format(pattern)
        else:
            args = ""

        return get("{}/dishes{}".format(self.address, args),
                field='dishes')

    def dish(self, hashid):
        return get("{}/dishes/{}".format(self.address, hashid),
                field='dish')

    def create(self, name):
        return post("{}/dishes/new".format(self.address),
                data={'name': name, 'directions': ''},
                field='dish')

    def save(self, dish_data):
        return post("{}/dishes/import".format(self.address),
                data={'json': json.dumps(dish_data)},
                field='dish')

    def delete(self, hashid):
        return delete("{}/dishes/{}".format(self.address, hashid),
                field=None)

    def set_ingredient(self, dish, ingredient, quantity):
        return post("{}/dishes/{}/ingredient".format(self.address, dish.get('id')),
                data={'ingredient': ingredient, 'quantity': quantity},
                field=None)

