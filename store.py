from dish import Dish
from ingredient import Ingredient
import drivers

class store:
    def __init__(self, driver):
        self.driver = driver

    def dish_lookup(self, query):
        return [Dish(params, self) for params in self.driver.lookup_dish(query)]

    @property
    def ingredients(self):
        return [Ingredient(params, self) for params in self.driver.get_ingredient({})]

    def save(self, dish):
        status, error = self.driver.put_dish(dish)
        return status, error

    def delete(self, query):
        return self.driver.delete_dish(query)

    def load(self, query):
        return [Dish(params, self) for params in self.driver.get_dish(query)]

    def load_one(self, query):
        results = self.load(query)

        if len(results) == 0:
            return (False, None, "Dish not found")

        return (True, results[0], "")

    def create(self, params):
        return Dish(params, self)

    def get_ingredient(self, params):
        params = {'name': params['ingredient']}
        stored = self.driver.get_ingredient(params)

        if len(stored):
            return Ingredient(stored[0], self)

        ingredient = Ingredient(params, self)
        self.driver.put_ingredient(ingredient)
        return ingredient

    def add(self, params):
        ing_list = self.driver.get_ingredient({'name': params['ingredient']})

        if len(ing_list) == 0:
            ing = Ingredient({'name': params['ingredient']}, self)
            self.driver.put_ingredient(ing)
        else:
            ing = Ingredient(ing_list[0], self)

        if params['quantity'] == '0':
            return self.driver.delete_requirement({'dish_id': params['dish'],
                                                   'ingredient_id': ing.id})

        if self.driver.exists_requirement({'dish_id': params['dish'],
                                            'ingredient_id': ing.id}):
            return self.driver.update_requirement({'dish_id': params['dish'],
                                                   'ingredient_id': ing.id},
                                                  {'quantity': params['quantity']})
        else:
            return self.driver.put_requirement({'dish_id': params['dish'],
                                                'ingredient_id': ing.id,
                                                'quantity': params['quantity']})

    def labels(self, stub=""):
        return self.driver.get_labels(stub)

    def new_label(self, name):
        return self.driver.put_label(name)
