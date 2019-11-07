from dish import Dish
from ingredient import Ingredient
import drivers

class store:
    def __init__(self, driver):
        self.driver = driver

    def dish_lookup(self, query):
        return [Dish(params, self) for params in self.driver.dish_lookup(query)]

    @property
    def ingredients(self):
        return [Ingredient(params, self) for params in self.driver.ingredient_get({})]

    def save(self, dish):
        status, error = self.driver.dish_put(dish)
        return status, error

    def delete(self, query):
        return self.driver.dish_delete(query)

    def load(self, query):
        return [Dish(params, self) for params in self.driver.dish_get(query)]

    def load_one(self, query):
        results = self.load(query)

        if len(results) == 0:
            return (False, None, "Dish not found")

        return (True, results[0], "")

    def create(self, params):
        return Dish(params, self)

    def get_ingredient(self, params):
        params = {'name': params['ingredient']}
        stored = self.driver.ingredient_get(params)

        if len(stored):
            return Ingredient(stored[0], self)

        ingredient = Ingredient(params, self)
        self.driver.ingredient_put(ingredient)
        return ingredient

    def add(self, params):
        ing_list = self.driver.ingredient_get({'name': params['ingredient']})

        if len(ing_list) == 0:
            ing = Ingredient({'name': params['ingredient']}, self)
            self.driver.ingredient_put(ing)
        else:
            ing = Ingredient(ing_list[0], self)

        if params['quantity'] == '0':
            return self.driver.requirement_delete({'dish_id': params['dish'],
                                                   'ingredient_id': ing.id})

        if self.driver.requirement_exists({'dish_id': params['dish'],
                                            'ingredient_id': ing.id}):
            return self.driver.requirement_update({'dish_id': params['dish'],
                                                   'ingredient_id': ing.id},
                                                  {'quantity': params['quantity']})
        else:
            return self.driver.requirement_put({'dish_id': params['dish'],
                                                'ingredient_id': ing.id,
                                                'quantity': params['quantity']})

    def labels(self, stub=""):
        return self.driver.label_get(stub)

    def new_label(self, name):
        return self.driver.label_put(name)
