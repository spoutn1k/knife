"""
store.py

Implementation of the Store class
"""

from flask import request, make_response
from knife import helpers
from knife.models import (Recipe, Label, Ingredient, Requirement, Tag,
                          Dependency)
from knife.exceptions import (
    InvalidValue,
    RecipeNotFound,
    RecipeAlreadyExists,
    RequirementNotFound,
    RequirementAlreadyExists,
    LabelNotFound,
    LabelAlreadyExists,
    TagNotFound,
    TagAlreadyExists,
    IngredientNotFound,
    IngredientAlreadyExists,
    IngredientInUse,
    DependencyNotFound,
    DepencyAlreadyExists,
    InvalidQuery,
    EmptyQuery,
    KnifeError,
)


def validate_query(args_dict, authorized_keys):
    for key in list(args_dict.keys()):
        if key not in authorized_keys:
            raise InvalidQuery({key, args_dict.get(key)})


def format_output(func):
    """
    Decoration, encasing the output of the function into a dict for it to be
    sent via the api.
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

    wrapper.__name__ = func.__name__.strip('_')
    return wrapper


def requirement_list(driver, recipe_id):
    data = driver.read(
        (Requirement, Ingredient, Requirement.fields.ingredient_id,
         Ingredient.fields.id),
        columns=(
            Ingredient.fields.id,
            Ingredient.fields.name,
            Requirement.fields.quantity,
        ),
        filters=[{
            Requirement.fields.recipe_id: recipe_id
        }])

    def _format(record):
        return {
            'ingredient': {
                Ingredient.fields.id: record[Ingredient.fields.id],
                Ingredient.fields.name: record[Ingredient.fields.name],
            },
            Requirement.fields.quantity: record[Requirement.fields.quantity]
        }

    return list(map(_format, data))


def dependency_list(driver, recipe_id):
    data = driver.read(
        (Recipe, Dependency, Recipe.fields.id, Dependency.fields.requisite),
        columns=(
            Recipe.fields.id,
            Recipe.fields.name,
            Dependency.fields.quantity,
        ),
        filters=[{
            Dependency.fields.required_by: recipe_id
        }])

    def _format(record):
        return {
            'recipe': {
                Recipe.fields.id: record[Recipe.fields.id],
                Recipe.fields.name: record[Recipe.fields.name],
            },
            Dependency.fields.quantity: record[Dependency.fields.quantity]
        }

    return list(map(_format, data))


def tag_list(driver, recipe_id):
    return driver.read((Tag, Label, Tag.fields.label_id, Label.fields.id),
                       filters=[{
                           Tag.fields.recipe_id: recipe_id
                       }],
                       columns=[Label.fields.name, Label.fields.id])


class Store:
    """
    Class acting as the middleman between the api front and the database driver
    This abstracts the methods of the driver for them to be interchangeable
    """

    def __init__(self, driver):
        self.driver = driver()

        for method in [
                self._dependency_add,
                self._dependency_delete,
                self._dependency_edit,
                self._ingredient_create,
                self._ingredient_delete,
                self._ingredient_edit,
                self._ingredient_lookup,
                self._ingredient_show,
                self._label_create,
                self._label_delete,
                self._label_edit,
                self._label_lookup,
                self._label_show,
                self._recipe_create,
                self._recipe_delete,
                self._recipe_edit,
                self._recipe_get,
                self._recipe_lookup,
                self._recipe_requirements,
                self._recipe_dependencies,
                self._recipe_tags,
                self._requirement_add,
                self._requirement_delete,
                self._requirement_edit,
                self._tag_add,
                self._tag_delete,
        ]:
            formatted = format_output(method)
            self.__setattr__(formatted.__name__, formatted)

    #  _                          _ _            _
    # (_)_ __   __ _ _ __ ___  __| (_) ___ _ __ | |_
    # | | '_ \ / _` | '__/ _ \/ _` | |/ _ \ '_ \| __|
    # | | | | | (_| | | |  __/ (_| | |  __/ | | | |_
    # |_|_| |_|\__, |_|  \___|\__,_|_|\___|_| |_|\__|
    #          |___/

    def _ingredient_create(self):
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

    def _ingredient_lookup(self):
        """
        Get an ingredient list, matching the parameters passed in args
        """
        args = helpers.fix_args(dict(request.args))
        validate_query(args, [Ingredient.fields.id, Ingredient.fields.name])

        if args.get(Ingredient.fields.name):
            args[Ingredient.fields.simple_name] = helpers.simplify(
                args.pop(Ingredient.fields.name))

        return self.driver.read(
            Ingredient,
            filters=[args],
            columns=[Ingredient.fields.id, Ingredient.fields.name],
            exact=False)

    def _ingredient_show(self, ingredient_id):
        """
        Show recipes tagged with the ingredient
        """
        if not (stored := self.driver.read(
                Ingredient, filters=[{
                    Ingredient.fields.id: ingredient_id
                }])):
            raise LabelNotFound(ingredient_id)

        recipes = self.driver.read(
            (Requirement, Recipe, Requirement.fields.recipe_id,
             Recipe.fields.id),
            filters=[{
                Requirement.fields.ingredient_id: ingredient_id
            }],
            columns=(Recipe.fields.id, Recipe.fields.name))

        ingredient = stored[0]
        ingredient.update({'used_in': recipes})

        return ingredient

    def _ingredient_delete(self, ingredient_id):
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

    def _ingredient_edit(self, ingredient_id):
        args = helpers.fix_args(dict(request.form))

        if not self.driver.read(Ingredient,
                                filters=[{
                                    Ingredient.fields.id: ingredient_id
                                }]):
            raise IngredientNotFound(ingredient_id)

        validate_query(args, [Ingredient.fields.name])

        if Ingredient.fields.name in args:
            name = args[Ingredient.fields.name]
            simple_name = helpers.simplify(name)

            if not simple_name:
                raise InvalidValue(Ingredient.fields.name, name)

            matching_names = self.driver.read(
                Ingredient,
                filters=[{
                    Ingredient.fields.simple_name: simple_name
                }])
            name_exists = list(
                filter(lambda i: i[Ingredient.fields.id] != ingredient_id,
                       matching_names))

            if name_exists:
                raise IngredientAlreadyExists(ingredients[0])

            args[Ingredient.fields.simple_name] = simple_name

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

    def _recipe_create(self):
        """
        Create a recipe object from the params in arguments
        """
        params = helpers.fix_args(dict(request.form))
        validate_query(params, [
            Recipe.fields.name, Recipe.fields.author, Recipe.fields.directions
        ])

        if not params:
            raise EmptyQuery()

        if Recipe.fields.name not in params.keys():
            raise InvalidQuery(params)

        recipe = Recipe(params)

        if not recipe.simple_name:
            raise InvalidValue(Recipe.fields.name, recipe.name)

        if recipes := self.driver.read(Recipe,
                                       filters=[{
                                           Recipe.fields.simple_name:
                                           recipe.simple_name
                                       }]):
            raise RecipeAlreadyExists(recipes[0])

        self.driver.write(Recipe, recipe.params)
        return recipe.serializable

    def _recipe_lookup(self):
        """
        Get a recipe list, matching the parameters passed in args
        """
        args = helpers.fix_args(dict(request.args))

        validate_query(args, [
            Recipe.fields.name, Recipe.fields.id, Recipe.fields.author,
            Recipe.fields.directions
        ])
        if args.get(Recipe.fields.name):
            args[Recipe.fields.simple_name] = helpers.simplify(
                args.pop(Recipe.fields.name))

        return self.driver.read(Recipe,
                                filters=[args],
                                columns=(Recipe.fields.id, Recipe.fields.name),
                                exact=False)

    def _recipe_delete(self, recipe_id):
        """
        Delete a recipe from an id
        """
        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        for requirement in self.driver.read(Requirement,
                                            filters=[{
                                                Requirement.fields.recipe_id:
                                                recipe_id
                                            }]):
            self.driver.erase(Requirement, filters=[requirement])

        for tag in self.driver.read(Tag,
                                    filters=[{
                                        Tag.fields.recipe_id: recipe_id
                                    }]):
            self.driver.erase(Tag, filters=[tag])

        for dependency in self.driver.read(Dependency,
                                           filters=[{
                                               Dependency.fields.required_by:
                                               recipe_id
                                           }]):
            self.driver.erase(Dependency, filters=[dependency])

        self.driver.erase(Recipe, filters=[{Recipe.fields.id: recipe_id}])

    def _recipe_get(self, recipe_id):
        """
        Get full details about the recipe of the specified id
        """
        if not (results := self.driver.read(
                Recipe, filters=[{
                    Recipe.fields.id: recipe_id
                }])):
            raise RecipeNotFound(recipe_id)

        recipe_data = results[0]

        recipe_data['requirements'] = requirement_list(self.driver, recipe_id)
        recipe_data['dependencies'] = dependency_list(self.driver, recipe_id)
        recipe_data['tags'] = tag_list(self.driver, recipe_id)

        return Recipe(recipe_data).serializable

    def _recipe_requirements(self, recipe_id):
        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        return requirement_list(self.driver, recipe_id)

    def _recipe_dependencies(self, recipe_id):
        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        return dependency_list(self.driver, recipe_id)

    def _recipe_tags(self, recipe_id):

        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        return tag_list(self.driver, recipe_id)

    def _recipe_edit(self, recipe_id):
        args = helpers.fix_args(dict(request.form))

        if not args:
            raise EmptyQuery()

        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        validate_query(args, [
            Recipe.fields.name, Recipe.fields.author, Recipe.fields.directions
        ])

        if Recipe.fields.name in args:
            name = args[Recipe.fields.name]
            simple_name = helpers.simplify(name)

            if not simple_name:
                raise InvalidValue(Recipe.fields.name, name)

            if recipes := self.driver.read(Recipe,
                                           filters=[{
                                               Recipe.fields.simple_name:
                                               simple_name
                                           }]):
                if recipes[0]['id'] != recipe_id:
                    raise RecipeAlreadyExists(recipes[0])

            args[Recipe.fields.simple_name] = simple_name

        self.driver.write(Recipe,
                          args,
                          filters=[{
                              Recipe.fields.id: recipe_id
                          }])

        return self._recipe_get(recipe_id)

    def _tag_add(self, recipe_id):
        """
        Tag a recipe with a label
        """
        args = helpers.fix_args(dict(request.form))

        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        label = Label(args)

        if not label.simple_name or " " in label.name:
            raise InvalidValue(Label.fields.name, label.name)

        if stored := self.driver.read(Label,
                                      filters=[{
                                          Label.fields.simple_name:
                                          label.simple_name
                                      }]):

            label = Label(stored[0])
        else:
            self.driver.write(Label, label.params)

        if self.driver.read(Tag,
                            filters=[{
                                Tag.fields.recipe_id: recipe_id,
                                Tag.fields.label_id: label.id
                            }]):
            raise TagAlreadyExists(recipe_id, label.id)

        self.driver.write(Tag, {
            Tag.fields.recipe_id: recipe_id,
            Tag.fields.label_id: label.id
        })

    def _tag_delete(self, recipe_id, label_id):
        """
        Untag a recipe with a label
        """
        if not self.driver.read(Label, filters=[{Label.fields.id: label_id}]):
            raise LabelNotFound(label_id)

        if not self.driver.read(Tag,
                                filters=[{
                                    Tag.fields.recipe_id: recipe_id,
                                    Tag.fields.label_id: label_id
                                }]):
            raise TagNotFound(recipe_id, label_id)

        self.driver.erase(Tag,
                          filters=[{
                              Tag.fields.recipe_id: recipe_id,
                              Tag.fields.label_id: label_id
                          }])

    def _dependency_add(self, recipe_id):
        """
        Specify a recipe requirement for a recipe
        """
        if not (required_id := request.form.get(Dependency.fields.requisite)):
            raise InvalidQuery(
                f"Missing parameter: {Dependency.fields.requisite}")

        if not (quantity := request.form.get(Dependency.fields.quantity)):
            raise InvalidQuery(
                f"Missing parameter: {Dependency.fields.quantity}")

        if recipe_id == required_id:
            raise InvalidValue(Dependency.fields.requisite, recipe_id)

        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: required_id
                                }]):
            raise RecipeNotFound(required_id)

        if self.driver.read(Dependency,
                            filters=[{
                                Dependency.fields.required_by: recipe_id,
                                Dependency.fields.requisite: required_id
                            }, {
                                Dependency.fields.required_by: required_id,
                                Dependency.fields.requisite: recipe_id
                            }]):
            raise DepencyAlreadyExists()

        self.driver.write(
            Dependency, {
                Dependency.fields.required_by: recipe_id,
                Dependency.fields.requisite: required_id,
                Dependency.fields.quantity: quantity,
            })

    def _dependency_edit(self, recipe_id, required_id):
        """
        Modify the quantity of a required recipe
        """
        args = helpers.fix_args(dict(request.form))
        validate_query(args, [Dependency.fields.quantity])

        if not args.get(Dependency.fields.quantity):
            raise InvalidValue(Dependency.fields.quantity, "")

        if not self.driver.read(
                Dependency,
                filters=[{
                    Dependency.fields.required_by: recipe_id,
                    Dependency.fields.requisite: required_id
                }]):
            raise DependencyNotFound(recipe_id, required_id)

        self.driver.write(Dependency,
                          args,
                          filters=[{
                              Dependency.fields.required_by: recipe_id,
                              Dependency.fields.requisite: required_id
                          }])

    def _dependency_delete(self, recipe_id, required_id):
        """
        Delete a recipe requirement for a recipe
        """
        if not self.driver.read(
                Dependency,
                filters=[{
                    Dependency.fields.required_by: recipe_id,
                    Dependency.fields.requisite: required_id
                }]):
            raise DependencyNotFound(recipe_id, required_id)

        self.driver.erase(Dependency,
                          filters=[{
                              Dependency.fields.required_by: recipe_id,
                              Dependency.fields.requisite: required_id
                          }])

    #                       _                               _
    #  _ __ ___  __ _ _   _(_)_ __ ___ _ __ ___   ___ _ __ | |_
    # | '__/ _ \/ _` | | | | | '__/ _ \ '_ ` _ \ / _ \ '_ \| __|
    # | | |  __/ (_| | |_| | | | |  __/ | | | | |  __/ | | | |_
    # |_|  \___|\__, |\__,_|_|_|  \___|_| |_| |_|\___|_| |_|\__|
    #              |_|

    def _requirement_add(self, recipe_id):
        """
        Add a requirement to a recipe
        """
        args = helpers.fix_args(request.form)
        validate_query(
            args,
            [Requirement.fields.quantity, Requirement.fields.ingredient_id])

        ingredient_id = args.get(Requirement.fields.ingredient_id)
        quantity = args.get(Requirement.fields.quantity)

        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        if not quantity:
            raise InvalidValue(Requirement.fields.quantity, quantity)

        if not self.driver.read(Ingredient,
                                filters=[{
                                    Ingredient.fields.id: ingredient_id
                                }]):
            raise IngredientNotFound(ingredient_id)

        if self.driver.read(Requirement,
                            filters=[{
                                Requirement.fields.recipe_id:
                                recipe_id,
                                Requirement.fields.ingredient_id:
                                ingredient_id
                            }]):
            raise RequirementAlreadyExists(recipe_id, ingredient_id)

        self.driver.write(
            Requirement, {
                Requirement.fields.recipe_id: recipe_id,
                Requirement.fields.ingredient_id: ingredient_id,
                Requirement.fields.quantity: quantity
            })

    def _requirement_edit(self, recipe_id, ingredient_id):
        """
        Modify the quantity of a required ingredient
        """
        args = helpers.fix_args(dict(request.form))
        validate_query(args, [Requirement.fields.quantity])

        if not args.get(Requirement.fields.quantity):
            raise InvalidValue(Requirement.fields.quantity,
                               args.get(Requirement.fields.quantity, ''))

        if not self.driver.read(
                Requirement,
                filters=[{
                    Requirement.fields.recipe_id: recipe_id,
                    Requirement.fields.ingredient_id: ingredient_id
                }]):
            raise RequirementNotFound(recipe_id, ingredient_id)

        self.driver.write(Requirement,
                          args,
                          filters=[{
                              Requirement.fields.recipe_id:
                              recipe_id,
                              Requirement.fields.ingredient_id:
                              ingredient_id
                          }])

    def _requirement_delete(self, recipe_id, ingredient_id):
        """
        Remove a requirement
        """
        if not self.driver.read(
                Requirement,
                filters=[{
                    Requirement.fields.recipe_id: recipe_id,
                    Requirement.fields.ingredient_id: ingredient_id
                }]):
            raise RequirementNotFound(recipe_id, ingredient_id)

        self.driver.erase(Requirement,
                          filters=[{
                              Requirement.fields.recipe_id:
                              recipe_id,
                              Requirement.fields.ingredient_id:
                              ingredient_id
                          }])

    def _label_lookup(self):
        """
        Get all labels which match the parameters in args
        """
        args = helpers.fix_args(dict(request.args))
        validate_query(args, [Label.fields.id, Label.fields.name])
        return self.driver.read(Label,
                                filters=[args],
                                columns=(Label.fields.id, Label.fields.name),
                                exact=False)

    def _label_delete(self, label_id):
        if not self.driver.read(Label, filters=[{Label.fields.id: label_id}]):
            raise LabelNotFound(label_id)

        for tag in self.driver.read(Tag,
                                    filters=[{
                                        Tag.fields.label_id: label_id
                                    }]):
            self.driver.erase(Tag, filters=[tag])

        self.driver.erase(Label, filters=[{Label.fields.id: label_id}])

    def _label_create(self):
        args = helpers.fix_args(dict(request.form))
        validate_query(args, [Label.fields.name])

        label = Label(args)

        if not label.simple_name or " " in label.name:
            raise InvalidValue(Label.fields.name, label.name)

        if stored := self.driver.read(Label,
                                      filters=[{
                                          Label.fields.simple_name:
                                          label.simple_name
                                      }]):

            raise LabelAlreadyExists(Label(stored[0]).serializable)
        else:
            self.driver.write(Label, label.params)

        return label.serializable

    def _label_show(self, label_id):
        """
        Show recipes tagged with the label
        """
        if not (stored := self.driver.read(Label,
                                           filters=[{
                                               Label.fields.id: label_id
                                           }])):
            raise LabelNotFound(label_id)

        recipes = self.driver.read(
            (Tag, Recipe, Tag.fields.recipe_id, Recipe.fields.id),
            filters=[{
                Tag.fields.label_id: label_id
            }],
            columns=(Recipe.fields.id, Recipe.fields.name))

        label = stored[0]
        label.update({'tagged_recipes': recipes})

        return label

    def _label_edit(self, label_id):
        args = helpers.fix_args(dict(request.form))

        if not self.driver.read(Label, filters=[{Label.fields.id: label_id}]):
            raise LabelNotFound(label_id)

        validate_query(args, [Label.fields.name])

        if Label.fields.name in args:
            name = args[Label.fields.name]
            simple_name = helpers.simplify(name)

            if not simple_name or ' ' in name:
                raise InvalidValue(Label.fields.name, name)

            if labels := self.driver.read(Label,
                                          filters=[{
                                              Label.fields.simple_name:
                                              simple_name
                                          }]):
                raise LabelAlreadyExists(labels[0])

            args[Label.fields.simple_name] = simple_name

        self.driver.write(Label, args, filters=[{Label.fields.id: label_id}])
