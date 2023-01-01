import sys
import os
import logging
from knife.models import OBJECTS
from knife.drivers.sqlite import SqliteDriver, model_definition

if __name__ == '__main__':
    driver = SqliteDriver()
    driver.setup()

    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

    for obj in OBJECTS:
        try:
            driver.connexion.execute(model_definition(obj))
        except Exception as e:
            print(repr(e), file=sys.stderr)
            pass

        #driver.connexion.execute("DELETE FROM %s" % obj.table_name)

    driver.close()
