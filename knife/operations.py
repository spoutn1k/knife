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
    df = Dependency.fields

    nodes = set()
    to_visit = {recipe_id}

    while to_visit:
        next_tier = set()

        for recipe_id in to_visit:
            for dependency in driver.read(Dependency,
                                          columns=(df.requisite, ),
                                          filters=[{
                                              df.required_by: recipe_id
                                          }]):
                next_tier.add(dependency[df.requisite])

        nodes = nodes | to_visit
        to_visit = next_tier - nodes

    return nodes


def requirement_list(driver, recipe_id):
    if_ = Ingredient.fields
    rf = Requirement.fields

    data = driver.read((Requirement, Ingredient, rf.ingredient_id, if_.id),
                       columns=(
                           if_.id,
                           if_.name,
                           rf.quantity,
                           rf.optional,
                           rf.group,
                       ),
                       filters=[{
                           rf.recipe_id: recipe_id
                       }])

    def _format(record):
        return {
            'ingredient': {
                if_.id.name: record[if_.id],
                if_.name.name: record[if_.name],
            },
            rf.quantity.name: record[rf.quantity],
            rf.optional.name: record[rf.optional],
            rf.group.name: record[Requirement.fields.group]
        }

    return list(map(_format, data))


def dependency_list(driver, recipe_id):
    rf = Recipe.fields
    df = Dependency.fields
    data = driver.read((Dependency, Recipe, df.requisite, rf.id),
                       columns=(
                           rf.id,
                           rf.name,
                           df.quantity,
                           df.optional,
                       ),
                       filters=[{
                           df.required_by: recipe_id
                       }])

    def _format(record):
        return {
            'recipe': {
                rf.id.name: record[rf.id],
                rf.name.name: record[rf.name],
            },
            df.quantity.name: record[df.quantity],
            df.optional.name: record[df.optional]
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
