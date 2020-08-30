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
BACK_END = Store(DRIVERS['pgsql'])


ROUTES = (
    (['GET'], BACK_END.ingredient_lookup, '/ingredients'),
    (['POST'], BACK_END.create_ingredient, '/ingredients/new'),
    (['PUT'], BACK_END.edit_ingredient, '/ingredients/<ingredient_id>'),
    (['DELETE'], BACK_END.delete_ingredient, '/ingredients/<ingredient_id>'),

    (['GET'], BACK_END.dish_lookup, '/dishes'),
    (['GET'], BACK_END.get_dish, '/dishes/<dish_id>'),
    (['POST'], BACK_END.create_dish, '/dishes/new'),
    (['PUT'], BACK_END.edit_dish, '/dishes/<dish_id>'),
    (['DELETE'], BACK_END.delete_dish, '/dishes/<dish_id>'),

    (['GET'], BACK_END.label_lookup, '/labels'),
    (['GET'], BACK_END.show_label, '/labels/<label_id>'),
    (['PUT'], BACK_END.edit_label, '/labels/<label_id>'),
    (['DELETE'], BACK_END.delete_label, '/labels/<label_id>'),

    (['GET'], BACK_END.show_requirements, '/dishes/<dish_id>/requirements'),
    (['POST'], BACK_END.add_requirement, '/dishes/<dish_id>/requirements/add'),
    (['PUT'], BACK_END.edit_requirement,
     '/dishes/<dish_id>/requirements/<ingredient_id>'),
    (['DELETE'], BACK_END.delete_requirement,
     '/dishes/<dish_id>/requirements/<ingredient_id>'),

    (['GET'], BACK_END.get_deps, '/dishes/<dish_id>/dependencies'),
    (['POST'], BACK_END.link_dish, '/dishes/<dish_id>/dependencies/add'),
    (['DELETE'], BACK_END.unlink_dish,
     '/dishes/<dish_id>/dependencies/<required_id>'),

    (['GET'], BACK_END.get_tags, '/dishes/<dish_id>/tags'),
    (['POST'], BACK_END.tag_dish, '/dishes/<dish_id>/tags/add'),
    (['DELETE'], BACK_END.untag_dish, '/dishes/<dish_id>/tags/<label_id>'),
)

for methods, view_func, rule in ROUTES:
    APP.add_url_rule(rule=rule,
                     endpoint=view_func.__name__,
                     view_func=view_func,
                     methods=methods)

if __name__ == '__main__':
    APP.run()
