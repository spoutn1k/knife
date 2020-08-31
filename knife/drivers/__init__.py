import sys
from importlib import import_module
from pkgutil import walk_packages


class Datatypes():
    integer = 0
    text = 1

    required = 10
    primary_key = 11
    foreign_key = 12


DISHES_STRUCTURE = ('dishes', (('id', Datatypes.text, Datatypes.primary_key),
                               ('name', Datatypes.text, Datatypes.required),
                               ('simple_name', Datatypes.text,
                                Datatypes.required),
                               ('author', Datatypes.text), ('directions',
                                                            Datatypes.text)))

INGREDIENTS_STRUCTURE = ('ingredients',
                         (('id', Datatypes.text, Datatypes.primary_key),
                          ('name', Datatypes.text, Datatypes.required),
                          ('simple_name', Datatypes.text, Datatypes.required)))

LABELS_STRUCTURE = ('labels', (('id', Datatypes.text, Datatypes.primary_key),
                               ('name', Datatypes.text, Datatypes.required),
                               ('simple_name', Datatypes.text,
                                Datatypes.required)))

REQUIREMENTS_STRUCTURE = ('requirements',
                          (('dish_id', Datatypes.text, Datatypes.primary_key),
                           ('ingredient_id', Datatypes.text,
                            Datatypes.primary_key), ('quantity',
                                                     Datatypes.text)))

TAGS_STRUCTURE = ('tags', (('dish_id', Datatypes.text, Datatypes.primary_key),
                           ('label_id', Datatypes.text,
                            Datatypes.primary_key)))


class AbstractDriver(object):
    pass


DRIVERS = {}

for _, module_name, _ in walk_packages(path=__path__, prefix=__name__ + '.'):
    import_module(name=module_name)
    driver_module = sys.modules[module_name]

    if name := driver_module.__getattribute__('DRIVER_NAME'):
        DRIVERS[name] = driver_module
