import os
import sys
import knife
from knife.drivers import DRIVERS
from knife.models import OBJECTS
from pkgutil import walk_packages
from importlib import import_module


def default(value):
    raise ValueError("Driver not found")


if __name__ == '__main__':
    serializer = default

    if not (driver_name := os.environ.get('DATABASE_TYPE')):
        raise ValueError("DATABASE_TYPE is not set. Possible values are: %s" %
                         ", ".join(DRIVERS.keys()))

    for _, module_name, _ in walk_packages(
            path=[knife.__path__[0] + "/drivers"], prefix='knife.drivers.'):
        import_module(name=module_name)
        driver_module = sys.modules[module_name]

        if driver_name == driver_module.__getattribute__('DRIVER_NAME'):
            serializer = driver_module.__getattribute__('model_definition')

    for obj in OBJECTS:
        print("%s;" % serializer(obj))
