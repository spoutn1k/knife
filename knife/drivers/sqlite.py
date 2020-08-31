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

    def read(self, table, filters=[{}], columns=['*'], exact=True):
        if isinstance(table, tuple) and len(table) == 4:
            table = "%s JOIN %s ON %s.%s = %s.%s" % (table[0], table[1], table[0], table[2], table[1], table[3])
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


    def write(self, table: str, record: dict) -> None:
        if table not in TABLES.keys():
            raise ValueError(table)
        
        columns = ', '.join(record.keys())
        values = ', '.join([":%s" % key for key in record.keys()])

        template = 'INSERT INTO %s (%s) VALUES (%s)' % (table, columns, values)
        parameters = record
        
        self.setup()
        # TODO log dat
        print(template, parameters)
        self.cursor.execute(template, parameters)
        data = self.cursor.fetchall()
        self.close()

    def erase(self, table: str, filters=[{}]) -> None:
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
        data = self.cursor.fetchall()
        self.close()

#      _       _        _
#   __| | __ _| |_ __ _| |__   __ _ ___  ___
#  / _` |/ _` | __/ _` | '_ \ / _` / __|/ _ \
# | (_| | (_| | || (_| | |_) | (_| \__ \  __/
#  \__,_|\__,_|\__\__,_|_.__/ \__,_|___/\___|


def db_setup(params=None):
    connexion = sqlite3.connect(DBPATH)
    if params:
        connexion.execute(params)
    cursor = connexion.cursor()

    return connexion, cursor


def db_close(connexion):
    connexion.commit()
    connexion.close()


def db_execute(template, values={}, params=None):
    connexion, cursor = db_setup(params)

    try:
        cursor.execute(template, values)
    finally:
        db_close(connexion)


def db_query(query_string, query_params=None, params=None, match=False):
    """
    Query wrapper
    We assume all query params keys are sanitized
    """
    connexion, cursor = db_setup(params)

    # The query is a matching one, we change the operator from '=' to ' like '
    operator = " LIKE " if match else "="
    if match:
        for (key, val) in query_params.items():
            query_params[key] = "%{}%".format(val)

    if query_params:
        keys = [
            "{}{}:{}".format(key, operator, key)
            for (key, _) in query_params.items()
        ]
        query_string = query_string + " WHERE " + " AND ".join(keys)

    try:
        cursor.execute(query_string, query_params)
        data = cursor.fetchall()
    finally:
        db_close(connexion)

    return data


def db_update(table,
              updated_vals={},
              matching_vals={},
              params=None,
              match=False):
    """
    Query wrapper
    We assume all query params keys are sanitized
    """
    connexion, cursor = db_setup(params)

    # The query is a matching one, we change the operator from '=' to ' like '
    operator = " LIKE " if match else "="
    if match:
        for (key, val) in matching_vals.items():
            matching_vals[key] = "%{}%".format(val)

    if matching_vals:
        replace = [
            "{}{}:{}".format(key, '=', key)
            for (key, _) in updated_vals.items()
        ]
        match = [
            "{}{}:{}_match".format(key, operator, key)
            for (key, _) in matching_vals.items()
        ]
        query_string = "UPDATE {} SET {} WHERE {}".format(
            table, ','.join(replace), ' AND '.join(match))

    for (key, value) in matching_vals.items():
        updated_vals["{}_match".format(key)] = value
    try:
        cursor.execute(query_string, updated_vals)
        data = cursor.fetchall()
    finally:
        db_close(connexion)

    return data


def db_drop_tables(tables):
    for name in tables:
        try:
            db_execute("DROP TABLE {}".format(name))
        except Exception as err:
            print("Error {}".format(err))


def db_translate_dict(query):
    query_string = " and ".join(
        ["{}='{}'".format(key, val) for (key, val) in query.items()])

    if query_string:
        return " where " + query_string
    return ""


#      _ _     _
#   __| (_)___| |__
#  / _` | / __| '_ \
# | (_| | \__ \ | | |
#  \__,_|_|___/_| |_|


def dish_update(dish_id, dish_data):
    db_update('dishes', dish_data, {'id': dish_id})


#  _                          _ _            _
# (_)_ __   __ _ _ __ ___  __| (_) ___ _ __ | |_
# | | '_ \ / _` | '__/ _ \/ _` | |/ _ \ '_ \| __|
# | | | | | (_| | | |  __/ (_| | |  __/ | | | |_
# |_|_| |_|\__, |_|  \___|\__,_|_|\___|_| |_|\__|
#          |___/


def ingredient_update(ingredient_id, ingredient_data):
    db_update('ingredients', ingredient_data, {'id': ingredient_id})


#                       _                               _
#  _ __ ___  __ _ _   _(_)_ __ ___ _ __ ___   ___ _ __ | |_
# | '__/ _ \/ _` | | | | | '__/ _ \ '_ ` _ \ / _ \ '_ \| __|
# | | |  __/ (_| | |_| | | | |  __/ | | | | |  __/ | | | |_
# |_|  \___|\__, |\__,_|_|_|  \___|_| |_| |_|\___|_| |_|\__|
#              |_|


def requirement_update(query, values):
    return db_update('requirements', values, query)


#  _       _          _
# | | __ _| |__   ___| |___
# | |/ _` | '_ \ / _ \ / __|
# | | (_| | |_) |  __/ \__ \
# |_|\__,_|_.__/ \___|_|___/


def label_update(label_id, label_data):
    db_update('labels', label_data, {'id': label_id})


if __name__ == "__main__":
    db_drop_tables([
        'dishes', 'ingredients', 'requirements', 'dependencies', 'labels',
        'tags'
    ])
    db_execute(TAGS_DEFINITION)
    db_execute(LABELS_DEFINITION)
    db_execute(DISHES_DEFINITION)
    db_execute(INGREDIENTS_DEFINITION)
    db_execute(REQUIREMENTS_DEFINITION)
    db_execute(DEPENDENCIES_DEFINITION)
