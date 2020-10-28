from knife.models import objects
from knife.drivers.sqlite import SqliteDriver, model_definition

if __name__ == '__main__':
    driver = SqliteDriver()
    driver.setup()

    for obj in objects:
        try:
            driver.connexion.execute(model_definition(obj))
        except:
            pass
        driver.connexion.execute("DELETE FROM %s" % obj.table_name)

    driver.close()
