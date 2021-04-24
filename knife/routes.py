import logging
from knife.store import Store
from knife.drivers import DRIVERS
from knife.helpers import complain

LOGGER = logging.getLogger(__name__)

driver_name = complain('DATABASE_TYPE')
if driver_name.lower() not in DRIVERS.keys():
    raise ValueError("DATABASE_TYPE is not valid. Possible values are: %s" %
                     ", ".join(DRIVERS.keys()))

LOGGER.info('Starting with driver %s', driver_name)
BACK_END = Store(DRIVERS[driver_name.lower()])

ROUTES = (
    (['GET'], BACK_END.ingredient_lookup, '/ingredients'),
    (['GET'], BACK_END.show_ingredient, '/ingredients/<ingredient_id>'),
    (['POST'], BACK_END.create_ingredient, '/ingredients/new'),
    (['PUT'], BACK_END.edit_ingredient, '/ingredients/<ingredient_id>'),
    (['DELETE'], BACK_END.delete_ingredient, '/ingredients/<ingredient_id>'),
    (['GET'], BACK_END.recipe_lookup, '/recipes'),
    (['GET'], BACK_END.get_recipe, '/recipes/<recipe_id>'),
    (['POST'], BACK_END.create_recipe, '/recipes/new'),
    (['PUT'], BACK_END.edit_recipe, '/recipes/<recipe_id>'),
    (['DELETE'], BACK_END.delete_recipe, '/recipes/<recipe_id>'),
    (['GET'], BACK_END.label_lookup, '/labels'),
    (['POST'], BACK_END.create_label, '/labels/new'),
    (['GET'], BACK_END.show_label, '/labels/<label_id>'),
    (['PUT'], BACK_END.edit_label, '/labels/<label_id>'),
    (['DELETE'], BACK_END.delete_label, '/labels/<label_id>'),
    (['GET'], BACK_END.show_requirements, '/recipes/<recipe_id>/requirements'),
    (['POST'], BACK_END.add_requirement,
     '/recipes/<recipe_id>/requirements/add'),
    (['PUT'], BACK_END.edit_requirement,
     '/recipes/<recipe_id>/requirements/<ingredient_id>'),
    (['DELETE'], BACK_END.delete_requirement,
     '/recipes/<recipe_id>/requirements/<ingredient_id>'),
    (['GET'], BACK_END.show_dependencies, '/recipes/<recipe_id>/dependencies'),
    (['POST'], BACK_END.add_dependency,
     '/recipes/<recipe_id>/dependencies/add'),
    (['DELETE'], BACK_END.delete_dependency,
     '/recipes/<recipe_id>/dependencies/<required_id>'),
    (['GET'], BACK_END.show_tags, '/recipes/<recipe_id>/tags'),
    (['POST'], BACK_END.add_tag, '/recipes/<recipe_id>/tags/add'),
    (['DELETE'], BACK_END.delete_tag, '/recipes/<recipe_id>/tags/<label_id>'),
)


def setup_routes(application):
    for methods, view_func, rule in ROUTES:
        application.add_url_rule(rule=rule,
                                 endpoint=view_func.__name__,
                                 view_func=view_func,
                                 methods=methods)
