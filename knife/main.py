"""
main.py

Declaration of routes available in the knife app
"""

import os
from flask import Flask, request
from knife import helpers
from knife.store import Store
from knife.drivers import DRIVERS

APP = Flask(__name__)

if not (driver_name := os.environ.get('DATABASE_TYPE')):
    raise ValueError("DATABASE_TYPE is not set. Possible values are: %s" % ", ".join(DRIVERS.keys()))

BACK_END = Store(DRIVERS[driver_name.lower()])


ROUTES = (
    (['GET'], BACK_END.ingredient_lookup, '/ingredients'),
    (['GET'], BACK_END.show_ingredient, '/ingredients/<ingredient_id>'),
    (['POST'], BACK_END.create_ingredient, '/ingredients/new'),
    (['PUT'], BACK_END.edit_ingredient, '/ingredients/<ingredient_id>'),
    (['DELETE'], BACK_END.delete_ingredient, '/ingredients/<ingredient_id>'),

    (['GET'], BACK_END.dish_lookup, '/dishes'),
    (['GET'], BACK_END.get_dish, '/dishes/<dish_id>'),
    (['POST'], BACK_END.create_dish, '/dishes/new'),
    (['PUT'], BACK_END.edit_dish, '/dishes/<dish_id>'),
    (['DELETE'], BACK_END.delete_dish, '/dishes/<dish_id>'),

    (['GET'], BACK_END.label_lookup, '/labels'),
    (['POST'], BACK_END.create_label, '/labels/new'),
    (['GET'], BACK_END.show_label, '/labels/<label_id>'),
    (['PUT'], BACK_END.edit_label, '/labels/<label_id>'),
    (['DELETE'], BACK_END.delete_label, '/labels/<label_id>'),

    (['GET'], BACK_END.show_requirements, '/dishes/<dish_id>/requirements'),
    (['POST'], BACK_END.add_requirement, '/dishes/<dish_id>/requirements/add'),
    (['PUT'], BACK_END.edit_requirement,
     '/dishes/<dish_id>/requirements/<ingredient_id>'),
    (['DELETE'], BACK_END.delete_requirement,
     '/dishes/<dish_id>/requirements/<ingredient_id>'),

    (['GET'], BACK_END.show_dependencies, '/dishes/<dish_id>/dependencies'),
    (['POST'], BACK_END.add_dependency, '/dishes/<dish_id>/dependencies/add'),
    (['DELETE'], BACK_END.delete_dependency,
     '/dishes/<dish_id>/dependencies/<required_id>'),

    (['GET'], BACK_END.show_tags, '/dishes/<dish_id>/tags'),
    (['POST'], BACK_END.add_tag, '/dishes/<dish_id>/tags/add'),
    (['DELETE'], BACK_END.delete_tag, '/dishes/<dish_id>/tags/<label_id>'),
)

for methods, view_func, rule in ROUTES:
    APP.add_url_rule(rule=rule,
                     endpoint=view_func.__name__,
                     view_func=view_func,
                     methods=methods)

if __name__ == '__main__':
    APP.run()
