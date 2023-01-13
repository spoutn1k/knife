import logging
from knife.store import Store
from knife.drivers import DRIVERS

LOGGER = logging.getLogger(__name__)

BACK_END = Store(None)

ROUTES = (
    (['GET'], BACK_END.ingredient_lookup, '/ingredients'),
    (['GET'], BACK_END.ingredient_show, '/ingredients/<ingredient_id>'),
    (['POST'], BACK_END.ingredient_create, '/ingredients/new'),
    (['PUT'], BACK_END.ingredient_edit, '/ingredients/<ingredient_id>'),
    (['DELETE'], BACK_END.ingredient_delete, '/ingredients/<ingredient_id>'),
    (['GET'], BACK_END.recipe_lookup, '/recipes'),
    (['GET'], BACK_END.recipe_get, '/recipes/<recipe_id>'),
    (['GET'], BACK_END.recipe_requirements,
     '/recipes/<recipe_id>/requirements'),
    (['GET'], BACK_END.recipe_dependencies,
     '/recipes/<recipe_id>/dependencies'),
    (['GET'], BACK_END.recipe_tags, '/recipes/<recipe_id>/tags'),
    (['POST'], BACK_END.recipe_create, '/recipes/new'),
    (['PUT'], BACK_END.recipe_edit, '/recipes/<recipe_id>'),
    (['DELETE'], BACK_END.recipe_delete, '/recipes/<recipe_id>'),
    (['GET'], BACK_END.label_lookup, '/labels'),
    (['POST'], BACK_END.label_create, '/labels/new'),
    (['GET'], BACK_END.label_show, '/labels/<label_id>'),
    (['PUT'], BACK_END.label_edit, '/labels/<label_id>'),
    (['DELETE'], BACK_END.label_delete, '/labels/<label_id>'),
    (['POST'], BACK_END.requirement_add,
     '/recipes/<recipe_id>/requirements/add'),
    (['PUT'], BACK_END.requirement_edit,
     '/recipes/<recipe_id>/requirements/<ingredient_id>'),
    (['DELETE'], BACK_END.requirement_delete,
     '/recipes/<recipe_id>/requirements/<ingredient_id>'),
    (['POST'], BACK_END.dependency_add,
     '/recipes/<recipe_id>/dependencies/add'),
    (['PUT'], BACK_END.dependency_edit,
     '/recipes/<recipe_id>/dependencies/<required_id>'),
    (['DELETE'], BACK_END.dependency_delete,
     '/recipes/<recipe_id>/dependencies/<required_id>'),
    (['POST'], BACK_END.tag_add, '/recipes/<recipe_id>/tags/add'),
    (['DELETE'], BACK_END.tag_delete, '/recipes/<recipe_id>/tags/<label_id>'),
)


def setup_routes(application, driver):
    BACK_END.driver = driver

    for methods, view_func, rule in ROUTES:
        application.add_url_rule(rule=rule,
                                 endpoint=view_func.__name__,
                                 view_func=view_func,
                                 methods=methods)
