"""
store.py

Implementation of the Store class
"""

import traceback
import werkzeug
from typing import Any
from flask import request, make_response
from knife import helpers
from knife.models.knife_model import Datatypes, Field
from knife.models import (
    Dependency,
    Ingredient,
    Label,
    Recipe,
    Requirement,
    Tag,
)
from knife.operations import (
    dependency_list,
    dependency_nodes,
    requirement_list,
    tag_list,
    classify,
)
from knife.exceptions import (
    DependencyAlreadyExists,
    DependencyCycle,
    DependencyNotFound,
    EmptyQuery,
    IngredientAlreadyExists,
    IngredientInUse,
    IngredientNotFound,
    InvalidQuery,
    InvalidValue,
    KnifeError,
    LabelAlreadyExists,
    LabelNotFound,
    RecipeAlreadyExists,
    RecipeNotFound,
    RequirementAlreadyExists,
    RequirementNotFound,
    TagAlreadyExists,
    TagNotFound,
)


def validate_query(
    args_dict: dict[str, str],
    authorized_fields: set[Field],
) -> dict[Field, str]:
    authorized_keys = set(map(lambda x: x.name, authorized_fields))

    for key in list(args_dict.keys()):
        if key not in authorized_keys:
            raise InvalidQuery({key: args_dict.get(key)})

    def _cast(datatype: set[Datatypes], arg: Any):
        if Datatypes.INTEGER in datatype:
            return int(arg)
        elif Datatypes.TEXT in datatype:
            return str(arg)
        elif Datatypes.BOOLEAN in datatype:
            return str(arg) in {'True', 'true'}
        raise InvalidValue(datatype)

    def _extract():
        for field in authorized_fields:
            if field.name in args_dict:
                try:
                    value = _cast(field.datatype, args_dict[field.name])
                except InvalidValue:
                    continue
                yield (field, value)

    return dict(_extract())


def _convert(form, model):
    for field in model.fields.fields:
        if field.name in form:
            yield (field, form.get(field.name))


def format_as_index(record, model):
    return {
        model.fields.id.name: record[model.fields.id],
        model.fields.name.name: record[model.fields.name],
    }


def format_output(func):
    """
    Decoration, encasing the output of the function into a dict for it to be
    sent via the api.
    Exceptions are caught and parsed to have a clear error message
    """

    def wrapper(*orig_args, **orig_kwargs):
        request_args = helpers.fix_args(dict(request.args))
        request_form = {}

        try:
            if request.is_json:
                request_form = request.get_json()
            data = func(*orig_args,
                        **orig_kwargs,
                        args=request_args,
                        form=request_form)
        except KnifeError as kerr:
            return make_response(({
                'accept': False,
                'error': str(kerr),
                'data': kerr.data
            }, kerr.status))
        except werkzeug.exceptions.BadRequest as err:
            return make_response(({
                'accept': False,
                'error': str(err),
                'data': None
            }, 400))
        except Exception as err:
            traceback.print_exc()
            return make_response(({
                'accept': False,
                'error': str(err),
                'data': None
            }, 500))
        return make_response(({'accept': True, 'data': data}, 200))

    wrapper.__name__ = func.__name__.strip('_')
    return wrapper


class Store:
    """
    Class acting as the middleman between the api front and the database driver
    This abstracts the methods of the driver for them to be interchangeable
    """

    def __init__(self, driver):
        self.driver = driver

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

    def _ingredient_create(self, args=None, form=None):
        """
        Create a ingredient object from the params in arguments
        """
        validate_query(form, [
            Ingredient.fields.name,
            Ingredient.fields.dairy,
            Ingredient.fields.meat,
            Ingredient.fields.gluten,
            Ingredient.fields.animal_product,
        ])

        if Ingredient.fields.name.name not in form.keys():
            raise InvalidQuery(form)

        ing = Ingredient(**form)

        if not ing.simple_name:
            raise InvalidValue(Ingredient.fields.name.name, ing.name)

        if stored := self.driver.read(Ingredient,
                                      filters=[{
                                          Ingredient.fields.simple_name:
                                          ing.simple_name
                                      }],
                                      exact=True):
            raise IngredientAlreadyExists(
                format_as_index(stored[0], Ingredient))

        self.driver.write(Ingredient, ing.params)
        return ing.serializable()

    def _ingredient_lookup(self, args=None, form=None):
        """
        Get an ingredient list, matching the parameters passed in args
        """
        filters = validate_query(args, [
            Ingredient.fields.id,
            Ingredient.fields.name,
        ])

        if pattern := filters.get(Ingredient.fields.name):
            filters[Ingredient.fields.simple_name] = helpers.simplify(pattern)
            filters.pop(Ingredient.fields.name)

        read = self.driver.read(
            Ingredient,
            filters=[filters],
            columns=[Ingredient.fields.id, Ingredient.fields.name],
            exact=False)

        format_ing = lambda x: format_as_index(x, Ingredient)

        return list(map(format_ing, read))

    def _ingredient_show(self, ingredient_id, args=None, form=None):
        """
        Show recipes tagged with the ingredient
        """
        if not (stored := self.driver.read(
                Ingredient, filters=[{
                    Ingredient.fields.id: ingredient_id
                }])):
            raise IngredientNotFound(ingredient_id)

        recipes = self.driver.read(
            (Requirement, Recipe, Requirement.fields.recipe_id,
             Recipe.fields.id),
            filters=[{
                Requirement.fields.ingredient_id: ingredient_id
            }],
            columns=(Recipe.fields.id, Recipe.fields.name))

        used_in = list(map(lambda x: format_as_index(x, Recipe), recipes))
        ingredient = Ingredient(stored[0]).serializable(used_in=used_in)

        return ingredient

    def _ingredient_delete(self, ingredient_id, args=None, form=None):
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

    def _ingredient_edit(self, ingredient_id, args=None, form=None):
        if not self.driver.read(Ingredient,
                                filters=[{
                                    Ingredient.fields.id: ingredient_id
                                }]):
            raise IngredientNotFound(ingredient_id)

        validate_query(form, [
            Ingredient.fields.name,
            Ingredient.fields.dairy,
            Ingredient.fields.meat,
            Ingredient.fields.gluten,
            Ingredient.fields.animal_product,
        ])

        if Ingredient.fields.name.name in form:
            name = form[Ingredient.fields.name.name]
            simple_name = helpers.simplify(name)

            if not simple_name:
                raise InvalidValue(Ingredient.fields.name.name, name)

            matching_names = self.driver.read(
                Ingredient,
                filters=[{
                    Ingredient.fields.simple_name: simple_name
                }])
            name_exists = list(
                filter(lambda i: i[Ingredient.fields.id] != ingredient_id,
                       matching_names))

            if name_exists:
                raise IngredientAlreadyExists(
                    format_as_index(name_exists[0], Ingredient))

            form[Ingredient.fields.simple_name.name] = simple_name

        self.driver.write(Ingredient,
                          dict(_convert(form, Ingredient)),
                          filters=[{
                              Ingredient.fields.id: ingredient_id
                          }])

    #      _ _     _
    #   __| (_)___| |__
    #  / _` | / __| '_ \
    # | (_| | \__ \ | | |
    #  \__,_|_|___/_| |_|

    def _recipe_create(self, args=None, form=None):
        """
        Create a recipe object from the params in arguments
        """
        validate_query(form, [
            Recipe.fields.name,
            Recipe.fields.author,
            Recipe.fields.information,
            Recipe.fields.directions,
        ])

        if not form:
            raise EmptyQuery()

        if Recipe.fields.name.name not in form:
            raise InvalidQuery(dict(name=None))

        recipe = Recipe(**form)

        if not recipe.simple_name:
            raise InvalidValue(Recipe.fields.name, recipe.name)

        if recipes := self.driver.read(Recipe,
                                       filters=[{
                                           Recipe.fields.simple_name:
                                           recipe.simple_name
                                       }]):
            raise RecipeAlreadyExists(format_as_index(recipes[0], Recipe))

        self.driver.write(Recipe, recipe.params)
        return recipe.serializable()

    def _recipe_lookup(self, args=None, form=None):
        """
        Get a recipe list, matching the parameters passed in args
        """
        filters = validate_query(args, [
            Recipe.fields.name,
            Recipe.fields.id,
            Recipe.fields.author,
            Recipe.fields.directions,
        ])

        if pattern := filters.get(Recipe.fields.name):
            filters[Recipe.fields.simple_name] = helpers.simplify(pattern)
            filters.pop(Recipe.fields.name)

        read = self.driver.read(Recipe,
                                filters=[filters],
                                columns=(Recipe.fields.id, Recipe.fields.name),
                                exact=False)

        format_recipe = lambda x: format_as_index(x, Recipe)

        return list(map(format_recipe, read))

    def _recipe_delete(self, recipe_id, args=None, form=None):
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

    def _recipe_get(self, recipe_id, args=None, form=None):
        """
        Get full details about the recipe of the specified id
        """
        rf = Recipe.fields
        if not (results := self.driver.read(Recipe,
                                            filters=[{
                                                rf.id: recipe_id
                                            }])):
            raise RecipeNotFound(recipe_id)

        extra = dict(
            requirements=requirement_list(self.driver, recipe_id),
            dependencies=dependency_list(self.driver, recipe_id),
            tags=tag_list(self.driver, recipe_id),
            classifications=classify(self.driver, recipe_id),
        )

        recipe_data = Recipe(results[0]).serializable(**extra)

        return recipe_data

    def _recipe_requirements(self, recipe_id, args=None, form=None):
        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        return requirement_list(self.driver, recipe_id)

    def _recipe_dependencies(self, recipe_id, args=None, form=None):
        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        return dependency_list(self.driver, recipe_id)

    def _recipe_tags(self, recipe_id, args=None, form=None):

        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        return tag_list(self.driver, recipe_id)

    def _recipe_edit(self, recipe_id, args=None, form=None):
        if not form:
            raise EmptyQuery()

        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        validate_query(form, [
            Recipe.fields.name,
            Recipe.fields.author,
            Recipe.fields.directions,
            Recipe.fields.information,
        ])

        if Recipe.fields.name.name in form:
            name = form[Recipe.fields.name.name]
            simple_name = helpers.simplify(name)

            if not simple_name:
                raise InvalidValue(Recipe.fields.name.name, name)

            if recipes := self.driver.read(Recipe,
                                           filters=[{
                                               Recipe.fields.simple_name:
                                               simple_name
                                           }]):
                if recipes[0][Recipe.fields.id] != recipe_id:
                    raise RecipeAlreadyExists(
                        format_as_index(recipes[0], Recipe))

            form[Recipe.fields.simple_name.name] = simple_name

        self.driver.write(Recipe,
                          dict(_convert(form, Recipe)),
                          filters=[{
                              Recipe.fields.id: recipe_id
                          }])

        return self._recipe_get(recipe_id)

    def _tag_add(self, recipe_id, args=None, form=None):
        """
        Tag a recipe with a label
        """
        validate_query(form, [Label.fields.name])

        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        label = Label(**form)

        if not label.simple_name or " " in label.name:
            raise InvalidValue(Label.fields.name, label.name)

        if stored := self.driver.read(Label,
                                      filters=[{
                                          Label.fields.simple_name:
                                          label.simple_name
                                      }]):
            label = Label(**format_as_index(stored[0], Label))
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

    def _tag_delete(self, recipe_id, label_id, args=None, form=None):
        """
        Untag a recipe with a label
        """
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

    def _dependency_add(self, recipe_id, args=None, form=None):
        """
        Specify a recipe requirement for a recipe
        """
        params = validate_query(form, [
            Dependency.fields.requisite,
            Dependency.fields.quantity,
            Dependency.fields.optional,
        ])

        params[Dependency.fields.required_by] = recipe_id

        # Check the request contains the minimum fields
        if not (required_id := params.get(Dependency.fields.requisite)):
            raise InvalidQuery(
                f"Missing parameter: {Dependency.fields.requisite.name}")

        # Check the dependency does not link itself
        if recipe_id == required_id:
            raise InvalidValue(Dependency.fields.requisite, recipe_id)

        # Check the recipes exist
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

        # Check the dependency does not exist
        if self.driver.read(Dependency,
                            filters=[{
                                Dependency.fields.required_by: recipe_id,
                                Dependency.fields.requisite: required_id
                            }]):
            raise DependencyAlreadyExists()

        # Assert the quantity field is present, or set it to default
        if not params.get(Dependency.fields.quantity):
            params[Dependency.fields.
                   quantity] = Dependency.fields.quantity.default

        # Assert the optional field is present, or set it to default
        if not params.get(Dependency.fields.optional):
            params[Dependency.fields.
                   optional] = Dependency.fields.optional.default

        # Check the dependency does not create a cycle
        if (recipe_id in dependency_nodes(self.driver, required_id)
                or required_id in dependency_nodes(self.driver, recipe_id)):
            raise DependencyCycle()

        self.driver.write(Dependency, params)

    def _dependency_edit(self, recipe_id, required_id, args=None, form=None):
        """
        Modify the quantity of a required recipe
        """
        params = validate_query(form, [
            Dependency.fields.quantity,
            Dependency.fields.optional,
        ])

        if not self.driver.read(
                Dependency,
                filters=[{
                    Dependency.fields.required_by: recipe_id,
                    Dependency.fields.requisite: required_id
                }]):
            raise DependencyNotFound(recipe_id, required_id)

        self.driver.write(Dependency,
                          params,
                          filters=[{
                              Dependency.fields.required_by: recipe_id,
                              Dependency.fields.requisite: required_id
                          }])

    def _dependency_delete(self, recipe_id, required_id, args=None, form=None):
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

    def _requirement_add(self, recipe_id, args=None, form=None):
        """
        Add a requirement to a recipe
        """
        validate_query(form, [
            Requirement.fields.ingredient_id,
            Requirement.fields.quantity,
            Requirement.fields.optional,
            Requirement.fields.group,
        ])

        if not self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.id: recipe_id
                                }]):
            raise RecipeNotFound(recipe_id)

        if not (ingredient_id := form.get(
                Requirement.fields.ingredient_id.name)):
            raise InvalidValue(Requirement.fields.ingredient_id, None)

        if not self.driver.read(Ingredient,
                                filters=[{
                                    Ingredient.fields.id: ingredient_id
                                }]):
            raise IngredientNotFound(ingredient_id)

        if not (quantity := form.get(Requirement.fields.quantity.name)):
            raise InvalidValue(Requirement.fields.quantity, quantity)

        if self.driver.read(Requirement,
                            filters=[{
                                Requirement.fields.recipe_id:
                                recipe_id,
                                Requirement.fields.ingredient_id:
                                ingredient_id
                            }]):
            raise RequirementAlreadyExists(recipe_id, ingredient_id)

        requirement = Requirement(**form, recipe_id=recipe_id)

        self.driver.write(Requirement, requirement.params)

    def _requirement_edit(self,
                          recipe_id,
                          ingredient_id,
                          args=None,
                          form=None):
        """
        Modify the quantity of a required ingredient
        """
        validate_query(form, [
            Requirement.fields.quantity,
            Requirement.fields.optional,
        ])

        if not self.driver.read(
                Requirement,
                filters=[{
                    Requirement.fields.recipe_id: recipe_id,
                    Requirement.fields.ingredient_id: ingredient_id
                }]):
            raise RequirementNotFound(recipe_id, ingredient_id)

        self.driver.write(Requirement,
                          dict(_convert(form, Requirement)),
                          filters=[{
                              Requirement.fields.recipe_id:
                              recipe_id,
                              Requirement.fields.ingredient_id:
                              ingredient_id
                          }])

    def _requirement_delete(self,
                            recipe_id,
                            ingredient_id,
                            args=None,
                            form=None):
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

    def _label_lookup(self, args=None, form=None):
        """
        Get all labels which match the parameters in args
        """
        filters = validate_query(args, [
            Label.fields.id,
            Label.fields.name,
        ])

        if Label.fields.name in filters:
            filters[Label.fields.name] = filters.pop(Label.fields.name)

        saved = self.driver.read(Label,
                                 filters=[filters],
                                 columns=(Label.fields.id, Label.fields.name),
                                 exact=False)

        format_label = lambda x: format_as_index(x, Label)

        return list(map(format_label, saved))

    def _label_delete(self, label_id, args=None, form=None):
        if not self.driver.read(Label, filters=[{Label.fields.id: label_id}]):
            raise LabelNotFound(label_id)

        for tag in self.driver.read(Tag,
                                    filters=[{
                                        Tag.fields.label_id: label_id
                                    }]):
            self.driver.erase(Tag, filters=[tag])

        self.driver.erase(Label, filters=[{Label.fields.id: label_id}])

    def _label_create(self, args=None, form=None):
        validate_query(form, [Label.fields.name])

        label = Label(**form)

        if not label.simple_name or " " in label.name:
            raise InvalidValue(Label.fields.name, label.name)

        if stored := self.driver.read(Label,
                                      filters=[{
                                          Label.fields.simple_name:
                                          label.simple_name
                                      }]):
            raise LabelAlreadyExists(format_as_index(stored[0], Label))
        else:
            self.driver.write(Label, label.params)

        return label.serializable

    def _label_show(self, label_id, args=None, form=None):
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

        format_label = lambda x: format_as_index(x, Label)
        format_recipe = lambda x: format_as_index(x, Recipe)

        label = format_label(stored[0])
        label.update({'tagged_recipes': list(map(format_recipe, recipes))})

        return label

    def _label_edit(self, label_id, args=None, form=None):

        if not self.driver.read(Label, filters=[{Label.fields.id: label_id}]):
            raise LabelNotFound(label_id)

        validate_query(form, [Label.fields.name])

        if Label.fields.name.name in form:
            name = form[Label.fields.name.name]
            simple_name = helpers.simplify(name)

            if not simple_name or ' ' in name:
                raise InvalidValue(Label.fields.name.name, name)

            if labels := self.driver.read(Label,
                                          filters=[{
                                              Label.fields.simple_name:
                                              simple_name
                                          }]):
                raise LabelAlreadyExists(format_as_index(labels[0], Label))

            form[Label.fields.simple_name.name] = simple_name

        self.driver.write(
            Label,
            dict(_convert(form, Label)),
            filters=[{
                Label.fields.id: label_id
            }],
        )
