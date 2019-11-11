from dish import Dish
from ingredient import Ingredient
import drivers

class store:
    def __init__(self, driver):
        self.driver = driver

    def dish_lookup(self, args):
        return [Dish(params, self) for params in self.driver.dish_lookup(args)]

    def ingredient_lookup(self, args):
        status, stored, error = self.driver.ingredient_lookup(args)
        return [Ingredient(params, self) for params in stored]

    def save_dish(self, dish):
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

    def save_ingredient(self, ingredient):
        status, error = self.driver.ingredient_put(ingredient)
        return status, error

    def delete(self, dish_id):
        results = self.driver.dish_get({'id': dish_id})

        if len(results) != 1:
            return (False, None, "Dish not found")

        status, error = self.driver.dish_delete({'id': dish_id})
        return (status, Dish(results[0], self).json, error)

    def load(self, query):
        return [Dish(params, self) for params in self.driver.dish_get(query)]

    def get_dish(self, dish_id):
        results = self.driver.dish_get({'id': dish_id})

        if len(results) != 1:
            return (False, None, "Dish not found")

        return (True, Dish(results[0], self).json, "")

    def create(self, params):
        return Dish(params, self)

    def create_ingredient(self, params):
        return Ingredient(params, self)

    def get_ingredient(self, params):
        params = {'name': params['ingredient']}
        status, stored, error = self.driver.ingredient_get(params)

        if len(stored):
            return Ingredient(stored[0], self)

        ingredient = Ingredient(params, self)
        self.driver.ingredient_put(ingredient)
        return ingredient

    def add_requirement(self, dish_id, ingredient_id, quantity):
        status, ing_list, error = self.driver.ingredient_get({'id': ingredient_id})

        if not status or len(ing_list) == 0:
            return status, None, "Ingredient does not exist"

        if self.driver.requirement_exists({'dish_id': dish_id,
                                            'ingredient_id': ingredient_id}):
            return False, None, "Requirement aleady exists"
        
        return self.driver.requirement_put({'dish_id': dish_id,
                                            'ingredient_id': ingredient_id,
                                            'quantity': quantity})

    def get_requirement(self, dish_id, ingredient_id):
        stored = self.driver.requirement_get({'dish_id': dish_id, 'ingredient_id': ingredient_id})
        if len(stored) != 1:
            return False, {}, "Requirement not found"
        return True, stored[0], ""

    def edit_requirement(self, dish_id, ingredient_id, quantity):
        return self.driver.requirement_update({'dish_id': dish_id,
                                               'ingredient_id': ingredient_id},
                                              {'quantity': quantity})

    def delete_requirement(self, dish_id, ingredient_id):
        return self.driver.requirement_delete({'dish_id': dish_id, 'ingredient_id': ingredient_id})

    def labels(self, stub=""):
        return self.driver.label_get(stub)

    def new_label(self, name):
        return self.driver.label_put(name)

    def delete_ingredient(self, ingredient_id):
        status, stored, error = self.driver.ingredient_get({'id': ingredient_id})

        if not status:
            return status, None, error
        if len(stored) == 0:
            return False, None, "Ingredient not found"

        status, stored, error = self.driver.requirement_get({'ingredient_id': ingredient_id})

        if not status:
            return status, None, error
        if len(stored) > 0:
            return False, None, "Ingredient in used in {} recipes".format(len(stored))

        status, error = self.driver.ingredient_delete(ingredient_id)
        return status, None, error

    def tag_dish(self, dish_id, tagname):
        test = self.labels(tagname)

        if not len(test):
            status, label, error = self.new_label(tagname)
        else:
            label = test[0]

        return self.driver.tag(dish_id, label.get('id'))

    def show_label(self, tagname):
        test = self.labels(tagname)
        if not len(test):
            return True, [], ""
        return self.driver.label_show(test[0].get('id'))
