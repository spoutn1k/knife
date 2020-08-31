"""
store.py

Implementation of the Store class
"""

from flask import request
from knife import helpers
from knife.models import Dish, Label, Ingredient
from knife.exceptions import *
from knife.drivers.sqlite import SqliteDriver, DISHES, INGREDIENTS, LABELS, REQUIREMENTS, TAGS, DEPENDENCIES


def validate_query(args_dict, authorized_keys):
    for key in list(args_dict.keys()):
        if key not in authorized_keys:
            raise InvalidQuery(key)


def format_output(func):
    """
    Decoration, encasing the output of the function into a dict for it to be sent via the api.
    Exceptions are caught and parsed to have a clear error message
    """
    def wrapper(*args, **kwargs):
        try:
            data = func(*args, **kwargs)
        except KnifeError as kerr:
            return {'accept': False, 'error': str(kerr), 'data': kerr.data}
        return {'accept': True, 'data': data}

    wrapper.__name__ = func.__name__
    return wrapper


class Store:
    """
    Class acting as the middleman between the api front and the database driver
    This abstracts the methods of the driver for them to be interchangeable
    """
    def __init__(self, driver):
        self.driver = driver

#  _                          _ _            _
# (_)_ __   __ _ _ __ ___  __| (_) ___ _ __ | |_
# | | '_ \ / _` | '__/ _ \/ _` | |/ _ \ '_ \| __|
# | | | | | (_| | | |  __/ (_| | |  __/ | | | |_
# |_|_| |_|\__, |_|  \___|\__,_|_|\___|_| |_|\__|
#          |___/

    @format_output
    def create_ingredient(self):
        """
        Create a ingredient object from the params in arguments
        """
        params = helpers.fix_args(dict(request.form))
        validate_query(params, ['name'])

        if 'name' not in params.keys():
            raise InvalidQuery(params)

        ingredient = Ingredient(params)

        if SqliteDriver().read(INGREDIENTS,
                               filters=[{
                                   'simple_name': ingredient.simple_name
                               }]):
            raise IngredientAlreadyExists(params)

        SqliteDriver().write(INGREDIENTS, ingredient.params)
        return ingredient.serializable

    @format_output
    def ingredient_lookup(self):
        """
        Get an ingredient list, matching the parameters passed in args
        """
        args = helpers.fix_args(dict(request.args))
        validate_query(args, ['id', 'name'])
        return SqliteDriver().read(INGREDIENTS,
                                   filters=[args],
                                   columns=['id', 'name'],
                                   exact=False)

    @format_output
    def delete_ingredient(self, ingredient_id):
        """
        Delete an ingredient from an id
        """
        if not SqliteDriver().read(INGREDIENTS,
                                   filters=[{
                                       'id': ingredient_id
                                   }]):
            raise IngredientNotFound(ingredient_id)

        stored = SqliteDriver().read(REQUIREMENTS,
                                     filters=[{
                                         'ingredient_id': ingredient_id
                                     }])
        if stored:
            raise IngredientInUse(len(stored))

        SqliteDriver().erase(INGREDIENTS, filters=[{'id': ingredient_id}])

    @format_output
    def edit_ingredient(self, ingredient_id):
        args = helpers.fix_args(dict(request.form))

        if not SqliteDriver().read(INGREDIENTS,
                                   filters=[{
                                       'id': ingredient_id
                                   }]):
            raise IngredientNotFound(ingredient_id)

        validate_query(args, ['name'])
        if 'name' in args:
            args['simple_name'] = helpers.simplify(args['name'])

        SqliteDriver().write(INGREDIENTS,
                             args,
                             filters=[{
                                 'id': ingredient_id
                             }])

#      _ _     _
#   __| (_)___| |__
#  / _` | / __| '_ \
# | (_| | \__ \ | | |
#  \__,_|_|___/_| |_|

    @format_output
    def create_dish(self):
        """
        Create a dish object from the params in arguments
        """
        params = helpers.fix_args(dict(request.form))
        validate_query(params, ['name', 'author', 'directions'])
        if 'name' not in params.keys():
            raise InvalidQuery(params)

        dish = Dish(params)

        if SqliteDriver().read(DISHES,
                               filters=[{
                                   'simple_name': dish.simple_name
                               }]):
            raise DishAlreadyExists(dish.name)

        SqliteDriver().write(DISHES, dish.params)
        return dish.serializable

    @format_output
    def dish_lookup(self):
        """
        Get a dish list, matching the parameters passed in args
        """
        args = helpers.fix_args(dict(request.args))

        validate_query(args, ['name', 'id', 'author', 'directions'])
        if args.get('name'):
            args['simple_name'] = helpers.simplify(args.pop('name'))

        return SqliteDriver().read(DISHES,
                                   filters=[args],
                                   columns=('id', 'name'),
                                   exact=False)

    @format_output
    def delete_dish(self, dish_id):
        """
        Delete a dish from an id
        """
        if not SqliteDriver().read(DISHES, filters=[{'id': dish_id}]):
            raise DishNotFound(dish_id)

        SqliteDriver().erase(DISHES, filters=[{'id': dish_id}])

    @format_output
    def get_dish(self, dish_id):
        """
        Get full details about the dish of the specified id
        """
        results = SqliteDriver().read(DISHES, filters=[{'id': dish_id}])

        if not results:
            raise DishNotFound(dish_id)

        dish_data = results[0]

        dish_data['requirements'] = self.show_requirements(dish_id).get('data')

        dish_data['tags'] = SqliteDriver().read(
            (TAGS, LABELS, 'label_id', 'id'),
            filters=[{
                'dish_id': dish_id
            }],
            columns=['name', 'label_id'])

        dish_data['dependencies'] = SqliteDriver().read(
            (DISHES, DEPENDENCIES, 'id', 'requisite'),
            filters=[{
                'required_by': dish_id
            }],
            columns=['id', 'name'])

        return Dish(dish_data).serializable

    @format_output
    def edit_dish(self, dish_id):
        args = helpers.fix_args(dict(request.form))

        if not SqliteDriver().read(DISHES, filters=[{'id': dish_id}]):
            raise DishNotFound(dish_id)

        validate_query(args, ['name', 'author', 'directions'])

        if 'name' in args:
            args['simple_name'] = helpers.simplify(args['name'])

        SqliteDriver().write(DISHES, args, filters=[{'id': dish_id}])

    @format_output
    def get_tags(self, dish_id):

        if not SqliteDriver().read(DISHES, filters=[{'id': dish_id}]):
            raise DishNotFound(dish_id)

        return SqliteDriver().read((TAGS, LABELS, 'label_id', 'id'),
                                   filters=[{
                                       'dish_id': dish_id
                                   }],
                                   columns=['name', 'label_id'])

    @format_output
    def tag_dish(self, dish_id):
        """
        Tag a dish with a label
        """
        args = helpers.fix_args(dict(request.form))

        if not SqliteDriver().read(DISHES, filters=[{'id': dish_id}]):
            raise DishNotFound(dish_id)

        label = self.create_label(args).get('data')
        if SqliteDriver().read(TAGS,
                               filters=[{
                                   'dish_id': dish_id,
                                   'label_id': label.get('id')
                               }]):
            raise TagAlreadyExists(dish_id, label.get('id'))

        SqliteDriver().write(TAGS, {
            'dish_id': dish_id,
            'label_id': label.get('id')
        })

    @format_output
    def untag_dish(self, dish_id, label_id):
        """
        Untag a dish with a label
        """
        if not SqliteDriver().read(LABELS, filters=[{'id': label_id}]):
            raise LabelNotFound(label_id)

        if not SqliteDriver().read(TAGS,
                                   filters=[{
                                       'dish_id': dish_id,
                                       'label_id': label_id
                                   }]):
            raise TagNotFound(dish_id, label_id)

        SqliteDriver().erase(TAGS,
                             filters=[{
                                 'dish_id': dish_id,
                                 'label_id': label_id
                             }])

    @format_output
    def get_deps(self, dish_id):
        if not SqliteDriver().read(DISHES, filters=[{'id': dish_id}]):
            raise DishNotFound(dish_id)

        return self.driver.dish_requires(dish_id)

    @format_output
    def link_dish(self, dish_id):
        """
        Specify a recipe requirement for a recipe
        """
        required_id = request.form.get('required')

        if not SqliteDriver().read(DISHES, filters=[{'id': dish_id}]):
            raise DishNotFound(dish_id)

        if not SqliteDriver().read(DISHES, filters=[{'id': required_id}]):
            raise DishNotFound(required_id)

        SqliteDriver().write(DEPENDENCIES, {
            'required_by': dish_id,
            'requisite': required_id
        })

    @format_output
    def unlink_dish(self, dish_id, required_id):
        """
        Delete a recipe requirement for a recipe
        """
        SqliteDriver().erase(DEPENDENCIES,
                             filters=[{
                                 'dish_id': dish_id,
                                 'required_id': required_id
                             }])

#                       _                               _
#  _ __ ___  __ _ _   _(_)_ __ ___ _ __ ___   ___ _ __ | |_
# | '__/ _ \/ _` | | | | | '__/ _ \ '_ ` _ \ / _ \ '_ \| __|
# | | |  __/ (_| | |_| | | | |  __/ | | | | |  __/ | | | |_
# |_|  \___|\__, |\__,_|_|_|  \___|_| |_| |_|\___|_| |_|\__|
#              |_|

    @format_output
    def show_requirements(self, dish_id):
        requirement_list = []
        for raw_data in SqliteDriver().read(REQUIREMENTS,
                                            filters=[{
                                                'dish_id': dish_id
                                            }]):
            results = SqliteDriver().read(INGREDIENTS,
                                          filters=[{
                                              'id':
                                              raw_data.get('ingredient_id')
                                          }])
            req = {
                'ingredient': results[0],
                'quantity': raw_data.get('quantity')
            }
            requirement_list.append(req)

        return requirement_list

    @format_output
    def add_requirement(self, dish_id):
        """
        Add a requirement to a dish
        """

        ingredient_id = request.form.get('ingredient')
        quantity = request.form.get('quantity')

        if not ingredient_id or not quantity:
            raise InvalidQuery("Missing parameter")

        if not SqliteDriver().read(DISHES, filters=[{'id': dish_id}]):
            raise DishNotFound(dish_id)

        if not SqliteDriver().read(INGREDIENTS,
                                   filters=[{
                                       'id': ingredient_id
                                   }]):
            raise IngredientNotFound(ingredient_id)

        if SqliteDriver().read(REQUIREMENTS,
                               filters=[{
                                   'dish_id': dish_id,
                                   'ingredient_id': ingredient_id
                               }]):
            raise RequirementAlreadyExists(dish_id, ingredient_id)

        SqliteDriver().write(
            REQUIREMENTS, {
                'dish_id': dish_id,
                'ingredient_id': ingredient_id,
                'quantity': quantity
            })

    @format_output
    def get_requirement(self, dish_id, ingredient_id):
        """
        Get a requirement from both the dish and the required ingredient
        """
        stored = SqliteDriver().read(REQUIREMENTS,
                                     filters=[{
                                         'dish_id': dish_id,
                                         'ingredient_id': ingredient_id
                                     }])
        if not stored:
            raise RequirementNotFound(dish_id, ingredient_id)
        return stored[0]

    @format_output
    def edit_requirement(self, dish_id, ingredient_id):
        """
        Modify the quantity of a required ingredient
        """
        args = helpers.fix_args(dict(request.form))
        validate_query(args, ['quantity'])
        if not SqliteDriver().read(REQUIREMENTS,
                                   filters=[{
                                       'dish_id': dish_id,
                                       'ingredient_id': ingredient_id
                                   }]):
            raise RequirementNotFound(dish_id, ingredient_id)

        SqliteDriver().write(REQUIREMENTS,
                             args,
                             filters=[{
                                 'dish_id': dish_id,
                                 'ingredient_id': ingredient_id
                             }])

    @format_output
    def delete_requirement(self, dish_id, ingredient_id):
        """
        Remove a requirement
        """
        if not SqliteDriver().read(REQUIREMENTS,
                                   filters=[{
                                       'dish_id': dish_id,
                                       'ingredient_id': ingredient_id
                                   }]):
            raise RequirementNotFound(dish_id, ingredient_id)

        SqliteDriver().erase(REQUIREMENTS,
                             filters=[{
                                 'dish_id': dish_id,
                                 'ingredient_id': ingredient_id
                             }])


#  _       _          _
# | | __ _| |__   ___| |
# | |/ _` | '_ \ / _ \ |
# | | (_| | |_) |  __/ |
# |_|\__,_|_.__/ \___|_|

    @format_output
    def label_lookup(self):
        """
        Get all labels which match the parameters in args
        """
        args = helpers.fix_args(dict(request.args))
        validate_query(args, ['name', 'id'])
        return SqliteDriver().read(LABELS,
                                   filters=[args],
                                   columns=('id', 'name'),
                                   exact=False)

    @format_output
    def delete_label(self, label_id):
        """
        Create a new label
        """
        if not SqliteDriver().read(LABELS, filters=[{'id': label_id}]):
            raise LabelNotFound(label_id)

        SqliteDriver().erase(LABELS, filters=[{'id': label_id}])

    @format_output
    def create_label(self, args):
        validate_query(args, ['name'])
        label = Label(args)
        if label.name in ["", None] or " " in label.name:
            raise LabelInvalid(labelname)

        stored = SqliteDriver().read(LABELS,
                                     filters=[{
                                         'simple_name': label.simple_name
                                     }])
        if not stored:
            SqliteDriver().write(LABELS, label.params)
        else:
            return stored[0]

        return label.serializable

    @format_output
    def show_label(self, label_id):
        """
        Show dishes tagged with the label
        """
        if not SqliteDriver().read(LABELS, filters=[{'id': label_id}]):
            raise LabelNotFound(label_id)

        return SqliteDriver().read((TAGS, DISHES, 'dish_id', 'id'),
                                   filters=[{
                                       'label_id': label_id
                                   }],
                                   columns=['id', 'name'])

    @format_output
    def edit_label(self, label_id):
        args = helpers.fix_args(dict(request.form))

        if not SqliteDriver().read(LABELS, filters=[{'id': label_id}]):
            raise LabelNotFound(label_id)

        validate_query(args, ['name'])
        if 'name' in args:
            args['simple_name'] = helpers.simplify(args['name'])

        SqliteDriver().write(LABELS, args, filters=[{'id': label_id}])
