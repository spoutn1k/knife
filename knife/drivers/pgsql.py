import os
import psycopg2
from knife import helpers
from knife.drivers import AbstractDriver

DRIVER_NAME = 'pgsql'
DBURL = os.environ.get('DATABASE_URL')

DISHES_DEFINITION = '''
CREATE TABLE dishes (
    id TEXT,
    name TEXT NOT NULL,
    simple_name TEXT,
    author TEXT,
    directions TEXT,
    PRIMARY KEY (id))
'''

DEPENDENCIES_DEFINITION = '''
CREATE TABLE dependencies (
    requisite TEXT NOT NULL,
    required_by TEXT NOT NULL,
    PRIMARY KEY (requisite, required_by),
    CONSTRAINT fk_requisite
        FOREIGN KEY (requisite)
        REFERENCES dishes (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_requirement
        FOREIGN KEY (required_by)
        REFERENCES dishes (id)
        ON DELETE CASCADE)
'''

INGREDIENTS_DEFINITION = '''
CREATE TABLE ingredients (
    id TEXT,
    name TEXT NOT NULL,
    simple_name TEXT,
    PRIMARY KEY (id))
'''

REQUIREMENTS_DEFINITION = '''
CREATE TABLE requirements (
    dish_id TEXT NOT NULL, 
    ingredient_id TEXT NOT NULL, 
    quantity TEXT, 
    PRIMARY KEY (dish_id, ingredient_id),
    CONSTRAINT fk_dish
        FOREIGN KEY (dish_id)
        REFERENCES dishes (id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_ingredient
        FOREIGN KEY (ingredient_id)
        REFERENCES ingredients (id) 
        ON DELETE CASCADE)
'''

LABELS_DEFINITION = '''
CREATE TABLE labels (
    id TEXT,
    name TEXT NOT NULL,
    simple_name TEXT,
    PRIMARY KEY (id))
'''

TAGS_DEFINITION = '''
CREATE TABLE tags (
    dish_id TEXT NOT NULL,
    label_id TEXT NOT NULL,
    PRIMARY KEY (dish_id, label_id),
    CONSTRAINT fk_dish
        FOREIGN KEY (dish_id)
        REFERENCES dishes (id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_label
        FOREIGN KEY (label_id)
        REFERENCES labels (id) 
        ON DELETE CASCADE)
'''

def match_string(filters: list, exact: bool):
    parameters = {}

    if valid_filters := list(filter(lambda x: x, filters)):
        match_operator = '=' if exact else 'LIKE'
        template = ' WHERE '

        rules = []
        for index, f in enumerate(valid_filters):
            rule = []
            for column, value in f.items():
                if not exact:
                    value = "%%%s%%" % value
                parameters.update({"%s_%d" % (column, index): value})
                rule.append("%s %s %%(%s_%d)s" % (column, match_operator, column, index))
            rules.append(" AND ".join(rule))

        template += " OR ".join(rules)

        return template, parameters
    return '', {}


def transaction(func):
    def wrapper(*args, **kwargs):
        driver, table_ref = args[:2]

        if isinstance(table_ref, tuple):
            table = (Tables.tokens.get(table_ref[0])[0],
                     Tables.tokens.get(table_ref[1])[0], *table_ref[2:])
        else:
            table = Tables.tokens.get(table_ref)[0]

        args = (driver, table, *args[2:])

        driver.setup()
        template, parameters = func(*args, **kwargs)
        print(template, parameters)
        driver.cursor.execute(template, parameters)

        try:
            data = driver.cursor.fetchall()
        except psycopg2.ProgrammingError:
            data = []

        driver.close()

        if 'columns' in func.__code__.co_varnames:
            if kwargs.get('columns', ['*']) == ['*']:
                structure = Tables.tokens.get(table_ref)
                columns = [field[0] for field in structure[1]]
            else:
                columns = kwargs['columns']
            data = [dict(zip(columns, record)) for record in data]

        return data

    wrapper.__name__ = func.__name__
    return wrapper


class PostGresDriver(AbstractDriver):
    def setup(self, params=None):
        self.connexion = psycopg2.connect(DBURL, sslmode='require')
        self.cursor = self.connexion.cursor()

    def close(self):
        self.connexion.commit()
        self.connexion.close()

    @transaction
    def read(self, table, filters=[], columns=['*'], exact=True):
        if isinstance(table, tuple) and len(table) == 4:
            table = "%s JOIN %s ON %s.%s = %s.%s" % (
                table[0], table[1], table[0], table[2], table[1], table[3])

        template = 'SELECT %s FROM %s' % (', '.join(columns), table)

        addendum, parameters = match_string(filters, exact)

        return template + addendum, parameters

    @transaction
    def write(self, table: str, record: dict, filters=[]) -> None:
        if filters:
            # if filters are there, we update values

            # Put a stamp in case a key is both a filter and a target
            values = ', '.join(
                ["%s = %%(record_%s)s" % (k, k) for k in record.keys()])
            stamped_record = dict([('record_' + k, v)
                                   for (k, v) in record.items()])

            template = 'UPDATE %s SET %s' % (table, values)

            addendum, parameters = match_string(filters, True)

            if not addendum:
                raise ValueError(filters)

            template += addendum
            parameters.update(stamped_record)

        else:
            # if not, a simple insert
            columns = ', '.join(record.keys())
            values = ', '.join(["%%(%s)s" % key for key in record.keys()])

            template = 'INSERT INTO %s (%s) VALUES (%s)' % (table, columns,
                                                            values)
            parameters = record

        return template, parameters

    @transaction
    def erase(self, table: str, filters=[]) -> None:
        template = 'DELETE FROM %s' % table

        addendum, parameters = match_string(filters, True)

        if not addendum:
            raise ValueError(filters)

        return template + addendum, parameters


DRIVER = PostGresDriver
