"""
store.py

Implementation of the Store class
"""

from dish import Dish
from ingredient import Ingredient
from exceptions import *

def validate_query(args_dict, authorized_keys):
    for key in list(args_dict.keys()):
        if key not in authorized_keys:
            raise InvalidQuery(key)

def dish_validate_query(query_params):
    validate_query(query_params, ['name', 'simple_name', 'id', 'author', 'directions'])

def ingredient_validate_query(query_params):
    validate_query(query_params, ['name', 'id'])

def tag_validate_query(query_params):
    validate_query(query_params, ['dish_id', 'label_id'])

def label_validate_query(query_params):
    validate_query(query_params, ['name', 'id'])

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

    def create_ingredient(self, params):
        """
        Create a ingredient object from the params in arguments. Does not record anything yet.
        """
        validate_query(params, ['name'])
        if 'name' not in params.keys():
            raise InvalidQuery(params)
        return Ingredient(params, self)

    def ingredient_lookup(self, args):
        """
        Get an ingredient list, matching the parameters passed in args
        """
        ingredient_validate_query(args)
        stored = self.driver.ingredient_get(args, match=True)
        return [Ingredient(params, self) for params in stored]

    def save_ingredient(self, ingredient):
        """
        Record an ingredient object
        """
        if self.driver.ingredient_get({'id': ingredient.id}):
            raise IngredientAlreadyExists(ingredient.id)
        self.driver.ingredient_put(ingredient)

    def delete_ingredient(self, ingredient_id):
        """
        Delete an ingredient from an id
        """
        stored = self.driver.ingredient_get({'id': ingredient_id})
        if not stored:
            raise IngredientNotFound(ingredient_id)

        stored = self.driver.requirement_get({'ingredient_id': ingredient_id})
        if stored:
            raise IngredientInUse(len(stored))

        self.driver.ingredient_delete(ingredient_id)

#      _ _     _
#   __| (_)___| |__
#  / _` | / __| '_ \
# | (_| | \__ \ | | |
#  \__,_|_|___/_| |_|

    def create_dish(self, params):
        """
        Create a dish object from the params in arguments. Does not record anything yet.
        """
        validate_query(params, ['name', 'author', 'directions'])
        if 'name' not in params.keys():
            raise InvalidQuery(params)
        return Dish(params, self)

    def dish_lookup(self, args):
        """
        Get a dish list, matching the parameters passed in args
        """
        dish_validate_query(args)
        stored = self.driver.dish_lookup(args)
        return [Dish(params, self) for params in stored]

    def save_dish(self, dish):
        """
        Record a dish object
        """
        if self.driver.dish_get({'simple_name': dish.simple_name}):
            raise DishAlreadyExists(dish.name)
        self.driver.dish_put(dish)

    def delete_dish(self, dish_id):
        """
        Delete a dish from an id
        """
        if not self.driver.dish_get({'id': dish_id}):
            raise DishNotFound(dish_id)
        self.driver.dish_delete(dish_id)

    def get_dish(self, dish_id):
        """
        Get full details about the dish of the specified id
        """
        results = self.driver.dish_get({'id': dish_id})
        if not results:
            raise DishNotFound(dish_id)
        dish_data = results[0]

        requirement_list = []
        requirements_data = self.driver.requirement_get({'dish_id': dish_id})
        for raw_data in requirements_data:
            results = self.driver.ingredient_get({'id': raw_data.get('ingredient_id')})
            req = {'ingredient': results[0], 'quantity': raw_data.get('quantity')}
            requirement_list.append(req)

        dish_data['requirements'] = requirement_list

        dish_data['tags'] = self.driver.tag_get({'dish_id': dish_id})
        dish_data['dependencies'] = self.driver.dish_requires(dish_id)

        return Dish(dish_data, self).serializable

    def tag_dish(self, dish_id, labelname):
        """
        Tag a dish with a label
        """
        if not self.driver.dish_get({'id': dish_id}):
            raise DishNotFound(dish_id)

        if labelname in [""] or " " in labelname:
            raise LabelInvalid(labelname)

        label_list = self.driver.label_get({'name': labelname})
        if not label_list:
            label = self.driver.label_put(labelname)
        else:
            label = label_list[0]

        if self.driver.tag_get({'dish_id': dish_id, 'label_id': label.get('id')}):
            raise TagAlreadyExists(dish_id, label.get('id'))

        return self.driver.dish_tag(dish_id, label.get('id'))

    def untag_dish(self, dish_id, labelid):
        """
        Untag a dish with a label
        """
        if not self.driver.label_get({'id': labelid}):
            raise LabelNotFound(labelid)
        if not self.driver.tag_get({'dish_id': dish_id, 'label_id': labelid}):
            raise TagNotFound(dish_id, labelid)
        return self.driver.dish_untag(dish_id, labelid)

    def link_dish(self, dish_id, required_id):
        """
        Specify a recipe requirement for a recipe
        """
        if not self.driver.dish_get({'id': dish_id}):
            raise DishNotFound(dish_id)
        if not self.driver.dish_get({'id': required_id}):
            raise DishNotFound(required_id)
        return self.driver.dish_link(dish_id, required_id)

    def unlink_dish(self, dish_id, required_id):
        """
        Delete a recipe requirement for a recipe
        """
        return self.driver.dish_unlink(dish_id, required_id)

#                       _                               _
#  _ __ ___  __ _ _   _(_)_ __ ___ _ __ ___   ___ _ __ | |_
# | '__/ _ \/ _` | | | | | '__/ _ \ '_ ` _ \ / _ \ '_ \| __|
# | | |  __/ (_| | |_| | | | |  __/ | | | | |  __/ | | | |_
# |_|  \___|\__, |\__,_|_|_|  \___|_| |_| |_|\___|_| |_|\__|
#              |_|

    def add_requirement(self, dish_id, ingredient_id, quantity):
        """
        Add a requirement to a dish
        """
        if not self.driver.dish_get({'id': dish_id}):
            raise DishNotFound(dish_id)

        ing_list = self.driver.ingredient_get({'id': ingredient_id})

        if not ing_list:
            raise IngredientNotFound(ingredient_id)

        if self.driver.requirement_exists({'dish_id': dish_id,
                                           'ingredient_id': ingredient_id}):
            raise RequirementAlreadyExists(dish_id, ingredient_id)

        self.driver.requirement_put({'dish_id': dish_id,
                                     'ingredient_id': ingredient_id,
                                     'quantity': quantity})

    def get_requirement(self, dish_id, ingredient_id):
        """
        Get a requirement from both the dish and the required ingredient
        """
        stored = self.driver.requirement_get({'dish_id': dish_id, 'ingredient_id': ingredient_id})
        if not stored:
            raise RequirementNotFound(dish_id, ingredient_id)
        return stored[0]

    def edit_requirement(self, dish_id, ingredient_id, quantity):
        """
        Modify the quantity of a required ingredient
        """
        if not self.driver.requirement_get({'dish_id': dish_id, 'ingredient_id': ingredient_id}):
            raise RequirementNotFound(dish_id, ingredient_id)
        return self.driver.requirement_update({'dish_id': dish_id,
                                               'ingredient_id': ingredient_id},
                                              {'quantity': quantity})

    def delete_requirement(self, dish_id, ingredient_id):
        """
        Remove a requirement
        """
        if not self.driver.requirement_get({'dish_id': dish_id, 'ingredient_id': ingredient_id}):
            raise RequirementNotFound(dish_id, ingredient_id)
        return self.driver.requirement_delete({'dish_id': dish_id, 'ingredient_id': ingredient_id})

#  _       _          _
# | | __ _| |__   ___| |
# | |/ _` | '_ \ / _ \ |
# | | (_| | |_) |  __/ |
# |_|\__,_|_.__/ \___|_|

    def label_lookup(self, args):
        """
        Get all labels which match the parameters in args
        """
        label_validate_query(args)
        return self.driver.label_get(args)

    def delete_label(self, labelid):
        """
        Create a new label
        """
        if not self.driver.label_get({'id':labelid}):
            raise LabelNotFound(labelid)
        return self.driver.label_delete(labelid)

    def show_label(self, labelid):
        """
        Show dishes tagged with the label
        """
        label_list = self.driver.label_get({'id': labelid})
        if not label_list:
            raise LabelNotFound(labelid)
        dish_list = self.driver.tag_show(labelid)
        return {label_list[0].get('name'): dish_list}
