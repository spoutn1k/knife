from knife.models import (
    Dependency,
    Ingredient,
    Label,
    Recipe,
    Requirement,
    Tag,
)


def dependency_nodes(driver, recipe_id: str) -> set[str]:
    """
    Recursively follow all dependencies from a recipe, and output all the
    encountered ids. This *should* terminate as a dependency cycle should not
    be allowed, but there is a failsafe just in case.
    """
    nodes = set()
    to_visit = {recipe_id}

    while to_visit:
        next_tier = set()

        for recipe_id in to_visit:
            for dependency in driver.read(
                    Dependency,
                    columns=(Dependency.fields.requisite, ),
                    filters=[{
                        Dependency.fields.required_by: recipe_id
                    }]):
                next_tier.add(dependency[Dependency.fields.requisite])

        nodes = nodes | to_visit
        to_visit = next_tier - nodes

    return nodes


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
                Ingredient.fields.id.name: record[Ingredient.fields.id],
                Ingredient.fields.name.name: record[Ingredient.fields.name],
            },
            Requirement.fields.quantity.name:
            record[Requirement.fields.quantity]
        }

    return list(map(_format, data))


def dependency_list(driver, recipe_id):
    data = driver.read(
        (Dependency, Recipe, Dependency.fields.requisite, Recipe.fields.id),
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
                Recipe.fields.id.name: record[Recipe.fields.id],
                Recipe.fields.name.name: record[Recipe.fields.name],
            },
            Dependency.fields.quantity.name: record[Dependency.fields.quantity]
        }

    return list(map(_format, data))


def tag_list(driver, recipe_id):
    data = driver.read((Tag, Label, Tag.fields.label_id, Label.fields.id),
                       filters=[{
                           Tag.fields.recipe_id: recipe_id
                       }],
                       columns=[Label.fields.name, Label.fields.id])

    def _format(record):
        return {
            Label.fields.id.name: record[Label.fields.id],
            Label.fields.name.name: record[Label.fields.name],
        }

    return list(map(_format, data))
