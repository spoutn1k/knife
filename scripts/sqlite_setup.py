from knife.models import OBJECTS
from knife.drivers.sqlite import SqliteDriver, model_definition

if __name__ == '__main__':
    driver = SqliteDriver()
    driver.setup()

    for obj in OBJECTS:
        driver.connexion.execute(model_definition(obj))
        driver.connexion.execute("DELETE FROM %s" % obj.table_name)

    driver.close()
