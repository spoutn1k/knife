import sqlite3
from knife import helpers
from knife.drivers import AbstractDriver, DISHES_STRUCTURE, INGREDIENTS_STRUCTURE, LABELS_STRUCTURE, REQUIREMENTS_STRUCTURE, TAGS_STRUCTURE

DRIVER_NAME = 'sqlite'

DBPATH = '/tmp/database.db'

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

DISHES = 'dishes'
DEPENDENCIES = 'dependencies'
INGREDIENTS = 'ingredients'
REQUIREMENTS = 'requirements'
LABELS = 'labels'
TAGS = 'tags'

TABLES = {
    DISHES: DISHES_STRUCTURE,
    DEPENDENCIES: None,
    INGREDIENTS: INGREDIENTS_STRUCTURE,
    REQUIREMENTS: REQUIREMENTS_STRUCTURE,
    LABELS: LABELS_STRUCTURE,
    TAGS: TAGS_STRUCTURE
}


def match_string(filters: list, exact: bool):
    parameters = {}

    if valid_filters := list(filter(lambda x: x, filters)):
        match_operator = '=' if exact else 'LIKE'
        template = ' WHERE '

        rules = []
        for f in valid_filters:
            rule = []
            for column, value in f.items():
                if not exact:
                    value = "%%%s%%" % value
                parameters.update({column: value})
                rule.append("%s %s :%s" % (column, match_operator, column))
            rules.append(" AND ".join(rule))

        template += " OR ".join(rules)

        return (template, parameters)
    return ('', {})


class SqliteDriver(AbstractDriver):
    def setup(self, params=None):
        self.connexion = sqlite3.connect(DBPATH)

        if params:
            self.connexion.execute(params)

        self.cursor = self.connexion.cursor()

    def close(self):
        self.connexion.commit()
        self.connexion.close()

    def read(self, table, filters=[], columns=['*'], exact=True):
        if isinstance(table, tuple) and len(table) == 4:
            table = "%s JOIN %s ON %s.%s = %s.%s" % (
                table[0], table[1], table[0], table[2], table[1], table[3])
        else:
            if table not in TABLES.keys():
                raise ValueError(table)

        template = 'SELECT %s FROM %s' % (', '.join(columns), table)

        addendum, parameters = match_string(filters, exact)

        self.setup()
        # TODO log dat
        print(template + addendum, parameters)
        self.cursor.execute(template + addendum, parameters)
        data = self.cursor.fetchall()
        self.close()

        # TODO factorize this at the common level
        if columns == ['*']:
            structure = TABLES.get(table)
            columns = [field[0] for field in structure[1]]

        return [dict(zip(columns, record)) for record in data]

    def write(self, table: str, record: dict, filters=[]) -> None:
        if table not in TABLES.keys():
            raise ValueError(table)

        if filters:
            # if filters are there, we update values

            # Put a stamp in case a key is both a filter and a target
            values = ', '.join(["%s = :record_%s" % (k, k) for k in record.keys()])
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
            values = ', '.join([":%s" % key for key in record.keys()])

            template = 'INSERT INTO %s (%s) VALUES (%s)' % (table, columns, values)
            parameters = record

        self.setup()
        # TODO log dat
        print(template, parameters)
        self.cursor.execute(template, parameters)
        self.close()

    def erase(self, table: str, filters=[]) -> None:
        if table not in TABLES.keys():
            raise ValueError(table)

        template = 'DELETE FROM %s' % table

        addendum, parameters = match_string(filters, True)

        if not addendum:
            raise ValueError(filters)

        self.setup()
        # TODO log dat
        print(template + addendum, parameters)
        self.cursor.execute(template + addendum, parameters)
        self.close()
