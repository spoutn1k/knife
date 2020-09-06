"""
store.py

Implementation of the Store class
"""

from flask import request, make_response
from knife import helpers
from knife.models import Dish, Label, Ingredient, Requirement, Tag, Dependency
from knife.exceptions import *


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
            return make_response(({
                'accept': False,
                'error': str(kerr),
                'data': kerr.data
            }, kerr.status))
        return make_response(({'accept': True, 'data': data}, 200))

    wrapper.__name__ = func.__name__
    return wrapper


class Store:
    """
    Class acting as the middleman between the api front and the database driver
    This abstracts the methods of the driver for them to be interchangeable
    """
    def __init__(self, driver):
        self.driver = driver()

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
        validate_query(params, [Ingredient.fields.name])

        if Ingredient.fields.name not in params.keys():
            raise InvalidQuery(params)

        ing = Ingredient(params)

        if not ing.simple_name:
            raise InvalidValue(Ingredient.fields.name, ing.name)

        if stored := self.driver.read(Ingredient,
                                      filters=[{
                                          Ingredient.fields.simple_name:
                                          ing.simple_name
                                      }]):
            raise IngredientAlreadyExists(Ingredient(stored[0]).serializable)

        self.driver.write(Ingredient, ing.params)
        return ing.serializable

    @format_output
    def ingredient_lookup(self):
        """
        Get an ingredient list, matching the parameters passed in args
        """
        args = helpers.fix_args(dict(request.args))
        validate_query(args, [Ingredient.fields.id, Ingredient.fields.name])
        return self.driver.read(
            Ingredient,
            filters=[args],
            columns=[Ingredient.fields.id, Ingredient.fields.name],
            exact=False)

    @format_output
    def delete_ingredient(self, ingredient_id):
        """
        Delete an ingredient from an id
        """
        if not self.driver.read(Ingredient,
                                filters=[{
                                    Ingredient.fields.id: ingredient_id
                                }]):
            raise IngredientNotFound(ingredient_id)

        stored = self.driver.read(Requirement,
                                  filters=[{
                                      Requirement.fields.ingredient_id:
                                      ingredient_id
                                  }])
        if stored:
            raise IngredientInUse(len(stored))

        self.driver.erase(Ingredient,
                          filters=[{
                              Ingredient.fields.id: ingredient_id
                          }])

    @format_output
    def edit_ingredient(self, ingredient_id):
        args = helpers.fix_args(dict(request.form))

        if not self.driver.read(Ingredient,
                                filters=[{
                                    Ingredient.fields.id: ingredient_id
                                }]):
            raise IngredientNotFound(ingredient_id)

        validate_query(args, [Ingredient.fields.name])

        if Ingredient.fields.name in args:
            args[Ingredient.fields.simple_name] = helpers.simplify(
                args[Ingredient.fields.name])
            if stored := self.driver.read(Ingredient, filters=[{Ingredient.fields.simple_name: args[Ingredient.fields.simple_name]}]):
                raise IngredientAlreadyExists({})

        self.driver.write(Ingredient,
                          args,
                          filters=[{
                              Ingredient.fields.id: ingredient_id
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
        validate_query(
            params,
            [Dish.fields.name, Dish.fields.author, Dish.fields.directions])
        if Dish.fields.name not in params.keys():
            raise InvalidQuery(params)

        dish = Dish(params)

        if not dish.simple_name:
            raise InvalidValue(Dish.fields.name, dish.name)

        if self.driver.read(Dish,
                            filters=[{
                                Dish.fields.simple_name: dish.simple_name
                            }]):
            raise DishAlreadyExists(dish.name)

        self.driver.write(Dish, dish.params)
        return dish.serializable

    @format_output
    def dish_lookup(self):
        """
        Get a dish list, matching the parameters passed in args
        """
        args = helpers.fix_args(dict(request.args))

        validate_query(args, [
            Dish.fields.name, Dish.fields.id, Dish.fields.author,
            Dish.fields.directions
        ])
        if args.get(Dish.fields.name):
            args[Dish.fields.simple_name] = helpers.simplify(
                args.pop(Dish.fields.name))

        return self.driver.read(Dish,
                                filters=[args],
                                columns=(Dish.fields.id, Dish.fields.name),
                                exact=False)

    @format_output
    def delete_dish(self, dish_id):
        """
        Delete a dish from an id
        """
        if not self.driver.read(Dish, filters=[{Dish.fields.id: dish_id}]):
            raise DishNotFound(dish_id)

        self.driver.erase(Dish, filters=[{Dish.fields.id: dish_id}])

    @format_output
    def get_dish(self, dish_id):
        """
        Get full details about the dish of the specified id
        """
        if not (results := self.driver.read(Dish,
                                            filters=[{
                                                Dish.fields.id: dish_id
                                            }])):
            raise DishNotFound(dish_id)

        dish_data = results[0]

        dish_data['requirements'] = self.list_requirements(dish_id)

        dish_data['tags'] = self.driver.read(
            (Tag, Label, Tag.fields.label_id, Label.fields.id),
            filters=[{
                Tag.fields.dish_id: dish_id
            }],
            columns=[Label.fields.id, Label.fields.name])

        dish_data['dependencies'] = self.driver.read(
            (Dish, Dependency, Dish.fields.id, Dependency.fields.requisite),
            filters=[{
                Dependency.fields.required_by: dish_id
            }],
            columns=[Dish.fields.id, Dish.fields.name])

        return Dish(dish_data).serializable

    @format_output
    def edit_dish(self, dish_id):
        args = helpers.fix_args(dict(request.form))

        if not self.driver.read(Dish, filters=[{Dish.fields.id: dish_id}]):
            raise DishNotFound(dish_id)

        validate_query(
            args,
            [Dish.fields.name, Dish.fields.author, Dish.fields.directions])

        if Dish.fields.name in args:
            if not args[Dish.fields.name]:
                raise InvalidQuery({Dish.fields.name: args[Dish.fields.name]})
            args[Dish.fields.simple_name] = helpers.simplify(
                args[Dish.fields.name])
            if stored := self.driver.read(Dish,
                                          filters=[{
                                              Dish.fields.simple_name:
                                              args[Dish.fields.simple_name]
                                          }]):
                raise DishAlreadyExists(Dish(stored[0]).id)

        self.driver.write(Dish, args, filters=[{Dish.fields.id: dish_id}])

    @format_output
    def show_tags(self, dish_id):

        if not self.driver.read(Dish, filters=[{Dish.fields.id: dish_id}]):
            raise DishNotFound(dish_id)

        return self.driver.read(
            (Tag, Label, Tag.fields.label_id, Label.fields.id),
            filters=[{
                Tag.fields.dish_id: dish_id
            }],
            columns=[Label.fields.name, Label.fields.id])

    @format_output
    def add_tag(self, dish_id):
        """
        Tag a dish with a label
        """
        args = helpers.fix_args(dict(request.form))

        if not self.driver.read(Dish, filters=[{Dish.fields.id: dish_id}]):
            raise DishNotFound(dish_id)

        label = self.get_or_create_label(args)

        label_id = label.id
        if self.driver.read(Tag,
                            filters=[{
                                Tag.fields.dish_id: dish_id,
                                Tag.fields.label_id: label_id
                            }]):
            raise TagAlreadyExists(dish_id, label_id)

        self.driver.write(Tag, {
            Tag.fields.dish_id: dish_id,
            Tag.fields.label_id: label_id
        })

    @format_output
    def delete_tag(self, dish_id, label_id):
        """
        Untag a dish with a label
        """
        if not self.driver.read(Label, filters=[{Label.fields.id: label_id}]):
            raise LabelNotFound(label_id)

        if not self.driver.read(Tag,
                                filters=[{
                                    Tag.fields.dish_id: dish_id,
                                    Tag.fields.label_id: label_id
                                }]):
            raise TagNotFound(dish_id, label_id)

        self.driver.erase(Tag,
                          filters=[{
                              Tag.fields.dish_id: dish_id,
                              Tag.fields.label_id: label_id
                          }])

    @format_output
    def show_dependencies(self, dish_id):
        if not self.driver.read(Dish, filters=[{Dish.fields.id: dish_id}]):
            raise DishNotFound(dish_id)

        return self.driver.read(
            (Dish, Dependency, Dish.fields.id, Dependency.fields.requisite),
            filters=[{
                Dependency.fields.required_by: dish_id
            }],
            columns=[Dish.fields.id, Dish.fields.name])

    @format_output
    def add_dependency(self, dish_id):
        """
        Specify a recipe requirement for a recipe
        """
        if not (required_id := request.form.get(Dependency.fields.requisite)):
            raise InvalidQuery("Missing parameter")

        if not self.driver.read(Dish, filters=[{Dish.fields.id: dish_id}]):
            raise DishNotFound(dish_id)

        if not self.driver.read(Dish, filters=[{Dish.fields.id: required_id}]):
            raise DishNotFound(required_id)

        if self.driver.read(Dependency,
                            filters=[{
                                Dependency.fields.required_by: dish_id,
                                Dependency.fields.requisite: required_id
                            }]):
            raise DepencyAlreadyExists()

        self.driver.write(
            Dependency, {
                Dependency.fields.required_by: dish_id,
                Dependency.fields.requisite: required_id
            })

    @format_output
    def delete_dependency(self, dish_id, required_id):
        """
        Delete a recipe requirement for a recipe
        """
        self.driver.erase(Dependency,
                          filters=[{
                              Dependency.fields.required_by: dish_id,
                              Dependency.fields.requisite: required_id
                          }])

#                       _                               _
#  _ __ ___  __ _ _   _(_)_ __ ___ _ __ ___   ___ _ __ | |_
# | '__/ _ \/ _` | | | | | '__/ _ \ '_ ` _ \ / _ \ '_ \| __|
# | | |  __/ (_| | |_| | | | |  __/ | | | | |  __/ | | | |_
# |_|  \___|\__, |\__,_|_|_|  \___|_| |_| |_|\___|_| |_|\__|
#              |_|

    def list_requirements(self, dish_id):
        requirement_list = []

        data = self.driver.read(
            (Requirement, Ingredient, Requirement.fields.ingredient_id,
             Ingredient.fields.id),
            columns=(Ingredient.fields.name, Requirement.fields.quantity,
                     Ingredient.fields.id),
            filters=[{
                Requirement.fields.dish_id: dish_id
            }])

        for record in data:
            requirement_list.append({
                'ingredient': {
                    Ingredient.fields.id: record[Ingredient.fields.id],
                    Ingredient.fields.name: record[Ingredient.fields.name],
                },
                Requirement.fields.quantity:
                record[Requirement.fields.quantity]
            })

        return requirement_list

    @format_output
    def show_requirements(self, dish_id):
        if not self.driver.read(Dish, filters=[{Dish.fields.id: dish_id}]):
            raise DishNotFound(dish_id)

        return self.list_requirements(dish_id)

    @format_output
    def add_requirement(self, dish_id):
        """
        Add a requirement to a dish
        """

        ingredient_id = request.form.get(Requirement.fields.ingredient_id)
        quantity = request.form.get(Requirement.fields.quantity)

        if not ingredient_id or not quantity:
            raise InvalidQuery("Missing parameter")

        if not self.driver.read(Dish, filters=[{Dish.fields.id: dish_id}]):
            raise DishNotFound(dish_id)

        if not self.driver.read(Ingredient,
                                filters=[{
                                    Ingredient.fields.id: ingredient_id
                                }]):
            raise IngredientNotFound(ingredient_id)

        if self.driver.read(Requirement,
                            filters=[{
                                Requirement.fields.dish_id:
                                dish_id,
                                Requirement.fields.ingredient_id:
                                ingredient_id
                            }]):
            raise RequirementAlreadyExists(dish_id, ingredient_id)

        self.driver.write(
            Requirement, {
                Requirement.fields.dish_id: dish_id,
                Requirement.fields.ingredient_id: ingredient_id,
                Requirement.fields.quantity: quantity
            })

    @format_output
    def get_requirement(self, dish_id, ingredient_id):
        """
        Get a requirement from both the dish and the required ingredient
        """
        stored = self.driver.read(Requirement,
                                  filters=[{
                                      Requirement.fields.dish_id:
                                      dish_id,
                                      Requirement.fields.ingredient_id:
                                      ingredient_id
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
        validate_query(args, [Requirement.fields.quantity])
        if not self.driver.read(
                Requirement,
                filters=[{
                    Requirement.fields.dish_id: dish_id,
                    Requirement.fields.ingredient_id: ingredient_id
                }]):
            raise RequirementNotFound(dish_id, ingredient_id)

        self.driver.write(Requirement,
                          args,
                          filters=[{
                              Requirement.fields.dish_id:
                              dish_id,
                              Requirement.fields.ingredient_id:
                              ingredient_id
                          }])

    @format_output
    def delete_requirement(self, dish_id, ingredient_id):
        """
        Remove a requirement
        """
        if not self.driver.read(
                Requirement,
                filters=[{
                    Requirement.fields.dish_id: dish_id,
                    Requirement.fields.ingredient_id: ingredient_id
                }]):
            raise RequirementNotFound(dish_id, ingredient_id)

        self.driver.erase(Requirement,
                          filters=[{
                              Requirement.fields.dish_id:
                              dish_id,
                              Requirement.fields.ingredient_id:
                              ingredient_id
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
        validate_query(args, [Label.fields.id, Label.fields.name])
        return self.driver.read(Label,
                                filters=[args],
                                columns=(Label.fields.id, Label.fields.name),
                                exact=False)

    @format_output
    def delete_label(self, label_id):
        """
        Create a new label
        """
        if not self.driver.read(Label, filters=[{Label.fields.id: label_id}]):
            raise LabelNotFound(label_id)

        self.driver.erase(Label, filters=[{Label.fields.id: label_id}])

    def get_or_create_label(self, parameters):
        target = Label(parameters)

        if not target.simple_name or " " in target.name:
            raise InvalidValue(Label.fields.name, target.name)

        if stored := self.driver.read(Label,
                                      filters=[{
                                          Label.fields.simple_name:
                                          target.simple_name
                                      }]):

            return Label(stored[0])
        else:
            self.driver.write(Label, target.params)
            return target

    @format_output
    def create_label(self):
        args = helpers.fix_args(dict(request.form))
        validate_query(args, [Label.fields.name])

        label = self.get_or_create_label(args)

        return label.serializable

    @format_output
    def show_label(self, label_id):
        """
        Show dishes tagged with the label
        """
        if not self.driver.read(Label, filters=[{Label.field.id: label_id}]):
            raise LabelNotFound(label_id)

        return self.driver.read(
            (Tag, Dish, Tag.fields.dish_id, Dish.fields.id),
            filters=[{
                Tag.fields.label_id: label_id
            }],
            columns=(Dish.fields.id, Dish.fields.name))

    @format_output
    def edit_label(self, label_id):
        args = helpers.fix_args(dict(request.form))

        if not self.driver.read(Label, filters=[{Label.fields.id: label_id}]):
            raise LabelNotFound(label_id)

        validate_query(args, [Label.fields.name])
        if Label.fields.name in args:
            args[Label.fields.simple_name] = helpers.simplify(
                args[Label.fields.name])
            if stored := self.driver.read(Label, filters=[{Label.fields.simple_name: args[Label.fields.simple_name]}]):
                raise LabelAlreadyExists({'name': args[Label.fields.name]})

        self.driver.write(Label, args, filters=[{Label.fields.id: label_id}])
