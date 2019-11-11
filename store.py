"""
store.py

Implementation of the Store class
"""

from dish import Dish
from ingredient import Ingredient

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
        return Ingredient(params, self)

    def ingredient_lookup(self, args):
        """
        Get an ingredient list, matching the parameters passed in args
        """
        status, stored, error = self.driver.ingredient_lookup(args)
        return status, [Ingredient(params, self) for params in stored], error

    def get_ingredient(self, ingredient_id):
        """
        Get an ingredient from an id
        """
        status, stored, error = self.driver.ingredient_get({'id': ingredient_id})

        if not status:
            return status, None, error
        if not stored:
            return False, None, "Ingredient not found"

        return True, Ingredient(stored[0], self), None

    def save_ingredient(self, ingredient):
        """
        Record an ingredient object
        """
        status, error = self.driver.ingredient_put(ingredient)
        return status, error

    def delete_ingredient(self, ingredient_id):
        """
        Delete an ingredient from an id
        """
        status, stored, error = self.driver.ingredient_get({'id': ingredient_id})

        if not status:
            return status, None, error
        if not stored:
            return False, None, "Ingredient not found"

        status, stored, error = self.driver.requirement_get({'ingredient_id': ingredient_id})

        if not status:
            return status, None, error
        if stored:
            return False, None, "Ingredient in used in {} recipes".format(len(stored))

        status, error = self.driver.ingredient_delete(ingredient_id)
        return status, None, error

#      _ _     _
#   __| (_)___| |__
#  / _` | / __| '_ \
# | (_| | \__ \ | | |
#  \__,_|_|___/_| |_|

    def create_dish(self, params):
        """
        Create a dish object from the params in arguments. Does not record anything yet.
        """
        return Dish(params, self)

    def dish_lookup(self, args):
        """
        Get a dish list, matching the parameters passed in args
        """
        status, stored, error = self.driver.dish_lookup(args)
        return status, [Dish(params, self) for params in stored], error

    def save_dish(self, dish):
        """
        Record a dish object
        """
        status, error = self.driver.dish_put(dish)

        if not status:
            return False, error

        for data in dish.requirements:
            self.driver.ingredient_put(data.get('ingredient'))
            self.driver.requirement_put({'dish_id': dish.id,
                                         'ingredient_id': data['ingredient'].id,
                                         'quantity': data['quantity']})
        #for data in dish.dependencies:
        #for data in dish.tags:

        return status, error

    def delete_dish(self, dish_id):
        """
        Delete a dish from an id
        """
        status, results, error = self.driver.dish_get({'id': dish_id})

        if not status:
            return status, None, error
        if not results:
            return False, None, "Dish not found"

        status, error = self.driver.dish_delete(dish_id)
        return status, Dish(results[0], self).serializable, error

    def get_dish(self, dish_id):
        """
        Get full details about the dish of the specified id
        """
        status, results, error = self.driver.dish_get({'id': dish_id})

        if not status:
            return False, None, error
        if not results:
            return False, None, "Dish not found"

        dish_data = results[0]

        requirement_list = []
        _, requirements_data, _ = self.driver.requirement_get({'dish_id': dish_id})
        for raw_data in requirements_data:
            _, results, _ = self.driver.ingredient_get({'id': raw_data.get('ingredient_id')})
            req = {'ingredient': results[0], 'quantity': raw_data.get('quantity')}
            requirement_list.append(req)

        dish_data['requirements'] = requirement_list

        #status, dependencies_data, error = db_query("SELECT id, name FROM depe
        #ndencies JOIN dishes ON requisite = id WHERE required_by = '{}'".format(_id))
        #status, tags_data, error = db_query("SELECT labels.id, labels.name FRO
        #M labels JOIN tags ON labels.id = label_id WHERE dish_id = '{}'".format(_id))

        return True, Dish(dish_data, self).serializable, ""

    def tag_dish(self, dish_id, tagname):
        """
        Tag a dish with a label
        """
        test = self.labels(tagname)

        if not test:
            _, label, _ = self.new_label(tagname)
        else:
            label = test[0]

        return self.driver.tag(dish_id, label.get('id'))

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
        status, ing_list, error = self.driver.ingredient_get({'id': ingredient_id})

        if not status:
            return status, None, error
        if not ing_list:
            return False, None, "Ingredient does not exist"

        if self.driver.requirement_exists({'dish_id': dish_id,
                                           'ingredient_id': ingredient_id}):
            return False, None, "Requirement aleady exists"

        return self.driver.requirement_put({'dish_id': dish_id,
                                            'ingredient_id': ingredient_id,
                                            'quantity': quantity})

    def get_requirement(self, dish_id, ingredient_id):
        """
        Get a requirement from both the dish and the required ingredient
        """
        stored = self.driver.requirement_get({'dish_id': dish_id, 'ingredient_id': ingredient_id})
        if len(stored) != 1:
            return False, {}, "Requirement not found"
        return True, stored[0], ""

    def edit_requirement(self, dish_id, ingredient_id, quantity):
        """
        Modify the quantity of a required ingredient
        """
        return self.driver.requirement_update({'dish_id': dish_id,
                                               'ingredient_id': ingredient_id},
                                              {'quantity': quantity})

    def delete_requirement(self, dish_id, ingredient_id):
        """
        Remove a requirement
        """
        return self.driver.requirement_delete({'dish_id': dish_id, 'ingredient_id': ingredient_id})

#  _       _          _
# | | __ _| |__   ___| |
# | |/ _` | '_ \ / _ \ |
# | | (_| | |_) |  __/ |
# |_|\__,_|_.__/ \___|_|

    def labels(self, stub=""):
        """
        Get all labels which names contain stub
        """
        return self.driver.label_get(stub)

    def new_label(self, name):
        """
        Create a new label
        """
        return self.driver.label_put(name)

    def show_label(self, tagname):
        """
        Show dishes tagged with the label `tagname`
        """
        test = self.labels(tagname)
        if not test:
            return True, [], ""
        return self.driver.label_show(test[0].get('id'))
