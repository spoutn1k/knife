import sys
from importlib import import_module
from pkgutil import walk_packages


class AbstractDriver(object):
    pass


DRIVERS = {}

for _, module_name, _ in walk_packages(path=__path__, prefix=__name__ + '.'):
    import_module(name=module_name)
    driver_module = sys.modules[module_name]

    if name := driver_module.__getattribute__('DRIVER_NAME'):
        DRIVERS[name] = driver_module.__getattribute__('DRIVER')
