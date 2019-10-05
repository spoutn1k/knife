from dish import Dish
from ingredient import ingredient
import drivers

class store:
    def __init__(self, driver):
        self.driver = driver

    @property
    def dishes(self):
        return [Dish(params) for params in self.driver.get_dish({})]

    @property
    def ingredients(self):
        return [ingredient(params) for params in self.driver.get_ingredient({})]

    def save(self, dish):
        return self.driver.put_dish(dish)

    def delete(self, query):
        return self.driver.delete_dish(query)

    def load(self, query):
        return [Dish(params) for params in self.driver.get_dish(query)]

    def create(self, params):
        return Dish(params, self)

    def add(self, params):
        ing_list = self.driver.get_ingredient({'name': params['ingredient']})

        if len(ing_list) == 0:
            ing = ingredient({'name': params['ingredient']})
            self.driver.put_ingredient(ing)
        else:
            ing = ingredient(ing_list[0])

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

if __name__ == "__main__":
    store = store(drivers.sqlite)
    store.save(dish({'name': 'Tartare', 'directions': 'A nice dish'}))
