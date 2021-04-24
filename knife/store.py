"""
store.py

Implementation of the Store class
"""

from flask import request, make_response
from knife import helpers
from knife.models import Recipe, Label, Ingredient, Requirement, Tag, Dependency
from knife.exceptions import *


def validate_query(args_dict, authorized_keys):
    for key in list(args_dict.keys()):
        if key not in authorized_keys:
            raise InvalidQuery({key, args_dict.get(key)})


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

    wrapper.__name__ = func.__name__.strip('_')
    return wrapper


class Store:
    """
    Class acting as the middleman between the api front and the database driver
    This abstracts the methods of the driver for them to be interchangeable
    """
    def __init__(self, driver):
        self.driver = driver()

        for method in [
                self._add_dependency, self._add_requirement, self._add_tag,
                self._create_ingredient, self._create_label,
                self._create_recipe, self._delete_dependency,
                self._delete_ingredient, self._delete_label,
                self._delete_recipe, self._delete_requirement,
                self._delete_tag, self._edit_ingredient, self._edit_label,
                self._edit_recipe, self._edit_requirement, self._get_recipe,
                self._get_requirement, self._ingredient_lookup,
                self._label_lookup, self._list_requirements,
                self._recipe_lookup, self._show_dependencies,
                self._show_ingredient, self._show_label,
                self._show_requirements, self._show_tags
        ]:
            formatted = format_output(method)
            self.__setattr__(formatted.__name__, formatted)

#  _                          _ _            _
# (_)_ __   __ _ _ __ ___  __| (_) ___ _ __ | |_
# | | '_ \ / _` | '__/ _ \/ _` | |/ _ \ '_ \| __|
# | | | | | (_| | | |  __/ (_| | |  __/ | | | |_
# |_|_| |_|\__, |_|  \___|\__,_|_|\___|_| |_|\__|
#          |___/

    def _create_ingredient(self):
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
        return self.driver.read(
            Ingredient,
            filters=[args],
            columns=[Ingredient.fields.id, Ingredient.fields.name],
            exact=False)

    def _show_ingredient(self, ingredient_id):
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
        ingredient.update({'used_in_recipes': recipes})

        return ingredient

    def _delete_ingredient(self, ingredient_id):
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

    def _edit_ingredient(self, ingredient_id):
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

            if stored := self.driver.read(Ingredient,
                                          filters=[{
                                              Ingredient.fields.simple_name:
                                              simple_name
                                          }]):
                raise IngredientAlreadyExists({})

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

    def _create_recipe(self):
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

        if self.driver.read(Recipe,
                            filters=[{
                                Recipe.fields.simple_name:
                                recipe.simple_name
                            }]):
            raise RecipeAlreadyExists(recipe.name)

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

    def _delete_recipe(self, recipe_id):
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
            self.driver.erase(dependency, filters=[dependency])

        self.driver.erase(Recipe, filters=[{Recipe.fields.id: recipe_id}])

    def _get_recipe(self, recipe_id):
        """
        Get full details about the recipe of the specified id
        """
        if not (results := self.driver.read(
                Recipe, filters=[{
                    Recipe.fields.id: recipe_id
                }])):
            raise RecipeNotFound(recipe_id)

        recipe_data = results[0]

        recipe_data['requirements'] = self._list_requirements(recipe_id)

        recipe_data['tags'] = self.driver.read(
            (Tag, Label, Tag.fields.label_id, Label.fields.id),
            filters=[{
                Tag.fields.recipe_id: recipe_id
            }],
            columns=[Label.fields.id, Label.fields.name])

        recipe_data['dependencies'] = self.driver.read(
            (Recipe, Dependency, Recipe.fields.id,
             Dependency.fields.requisite),
            filters=[{
                Dependency.fields.required_by: recipe_id
            }],
            columns=[Recipe.fields.id, Recipe.fields.name])

        return Recipe(recipe_data).serializable

    def _edit_recipe(self, recipe_id):
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

            stored = self.driver.read(Recipe,
                                      filters=[{
                                          Recipe.fields.simple_name:
                                          simple_name
                                      }])
            if len(stored) and stored[0]['id'] != recipe_id:
                raise RecipeAlreadyExists(Recipe(stored[0]).id)

            args[Recipe.fields.simple_name] = simple_name

        self.driver.write(Recipe,
                          args,
                          filters=[{
                              Recipe.fields.id: recipe_id
                          }])

        return self._get_recipe(recipe_id)

    def _show_tags(self, recipe_id):

        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        return self.driver.read(
            (Tag, Label, Tag.fields.label_id, Label.fields.id),
            filters=[{
                Tag.fields.recipe_id: recipe_id
            }],
            columns=[Label.fields.name, Label.fields.id])

    def _add_tag(self, recipe_id):
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

    def _delete_tag(self, recipe_id, label_id):
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

    def _show_dependencies(self, recipe_id):
        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        return self.driver.read((Recipe, Dependency, Recipe.fields.id,
                                 Dependency.fields.requisite),
                                filters=[{
                                    Dependency.fields.required_by:
                                    recipe_id
                                }],
                                columns=[Recipe.fields.id, Recipe.fields.name])

    def _add_dependency(self, recipe_id):
        """
        Specify a recipe requirement for a recipe
        """
        if not (required_id := request.form.get(Dependency.fields.requisite)):
            raise InvalidQuery("Missing parameter")

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
                Dependency.fields.requisite: required_id
            })

    def _delete_dependency(self, recipe_id, required_id):
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

    def _list_requirements(self, recipe_id):
        requirement_list = []

        data = self.driver.read(
            (Requirement, Ingredient, Requirement.fields.ingredient_id,
             Ingredient.fields.id),
            columns=(Ingredient.fields.name, Requirement.fields.quantity,
                     Ingredient.fields.id),
            filters=[{
                Requirement.fields.recipe_id: recipe_id
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

    def _show_requirements(self, recipe_id):
        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        return self._list_requirements(recipe_id)

    def _add_requirement(self, recipe_id):
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

    def _get_requirement(self, recipe_id, ingredient_id):
        """
        Get a requirement from both the recipe and the required ingredient
        """
        stored = self.driver.read(Requirement,
                                  filters=[{
                                      Requirement.fields.recipe_id:
                                      recipe_id,
                                      Requirement.fields.ingredient_id:
                                      ingredient_id
                                  }])
        if not stored:
            raise RequirementNotFound(recipe_id, ingredient_id)
        return stored[0]

    def _edit_requirement(self, recipe_id, ingredient_id):
        """
        Modify the quantity of a required ingredient
        """
        args = helpers.fix_args(dict(request.form))
        validate_query(args, [Requirement.fields.quantity])

        if not args[Requirement.fields.quantity]:
            raise InvalidValue(Requirement.fields.quantity,
                               args[Requirement.fields.quantity])

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

    def _delete_requirement(self, recipe_id, ingredient_id):
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


#  _       _          _
# | | __ _| |__   ___| |
# | |/ _` | '_ \ / _ \ |
# | | (_| | |_) |  __/ |
# |_|\__,_|_.__/ \___|_|

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

    def _delete_label(self, label_id):
        if not self.driver.read(Label, filters=[{Label.fields.id: label_id}]):
            raise LabelNotFound(label_id)

        for tag in self.driver.read(Tag,
                                    filters=[{
                                        Tag.fields.label_id: label_id
                                    }]):
            self.driver.erase(Tag, filters=[tag])

        self.driver.erase(Label, filters=[{Label.fields.id: label_id}])

    def _create_label(self):
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

    def _show_label(self, label_id):
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

    def _edit_label(self, label_id):
        args = helpers.fix_args(dict(request.form))

        if not self.driver.read(Label, filters=[{Label.fields.id: label_id}]):
            raise LabelNotFound(label_id)

        validate_query(args, [Label.fields.name])

        if Label.fields.name in args:
            name = args[Label.fields.name]
            simple_name = helpers.simplify(name)

            if not simple_name or ' ' in name:
                raise InvalidValue(Label.fields.name, name)

            if stored := self.driver.read(Label,
                                          filters=[{
                                              Label.fields.simple_name:
                                              simple_name
                                          }]):
                raise LabelAlreadyExists({Label.fields.name: name})

            args[Label.fields.simple_name] = simple_name

        self.driver.write(Label, args, filters=[{Label.fields.id: label_id}])
