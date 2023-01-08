import sys
import logging
from importlib import import_module
from pkgutil import walk_packages


class AbstractDriver:

    def __init__(self, database_location):
        self.database_location = database_location


DRIVERS = {}


def get_driver(database_type, database_location):
    if database_type.lower() not in DRIVERS:
        logging.error("Database backend not available: %s", str(database_type))
        return None
    return DRIVERS[database_type.lower()](database_location)


for _, module_name, _ in walk_packages(path=__path__, prefix=__name__ + '.'):
    try:
        import_module(name=module_name)
    except ModuleNotFoundError:
        continue

    driver_module = sys.modules[module_name]

    if name := driver_module.__getattribute__('DRIVER_NAME').lower():
        DRIVERS[name] = driver_module.__getattribute__('DRIVER')
