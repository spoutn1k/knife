import sqlite3
import helpers

DBPATH = '/var/lib/knife/database.db'
LOGFILE = 'queries.log'
LOGGING = False

def log(*args, **kwargs):
    if not LOGGING:
        return
    with open(LOGFILE, 'a') as logfile:
        logfile.write("{} {}\n".format(*args, dict(**kwargs)))

DISHES = '''
CREATE TABLE dishes (
    id TEXT,
    name TEXT NOT NULL,
    simple_name TEXT,
    author TEXT,
    desc TEXT,
    PRIMARY KEY (id))
'''

DEPENDENCIES = '''
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

INGREDIENTS = '''
CREATE TABLE ingredients (
    id text PRIMARY KEY, 
    name text)
'''

REQUIREMENTS = '''
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

LABELS = '''
CREATE TABLE labels (
    id TEXT,
    name TEXT NOT NULL,
    simple_name TEXT,
    PRIMARY KEY (id))
'''

TAGS = '''
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

def db_execute(template, values=None, params=None):
    connexion, cursor = db_setup(params)

    try:
        log(template, values)
        if values:
            cursor.execute(template, values)
        else:
            cursor.execute(template)
        status = True
        error = None
    except sqlite3.IntegrityError as err:
        status = False
        error = repr(err)

    db_close(connexion)
    return status, error

def db_query(query_string, query_params=None, params=None, search=False):
    """
    Query wrapper
    We assume all query params keys are sanitized
    """
    connexion, cursor = db_setup(params)
    operator = " LIKE " if search else "="

    if search:
        for (key, val) in query_params.items():
            query_params[key] = "%{}%".format(val)

    if query_params:
        keys = ["{}{}:{}".format(key, operator, key) for (key, _) in query_params.items()]
        query_string = query_string + " WHERE " + " AND ".join(keys)

    try:
        log(query_string, query_params)
        cursor.execute(query_string, query_params)
        status = True
        data = cursor.fetchall()
        error = None
    except sqlite3.IntegrityError as err:
        status = False
        data = []
        error = str(err)

    db_close(connexion)
    return status, data, error

def db_drop_tables(tables):
    for name in tables:
        try:
            db_execute("DROP TABLE {}".format(name))
        except Exception as err:
            print("Error {}".format(err))

def db_translate_dict(query):
    query_string = " and ".join(["{}='{}'".format(key, val) for (key, val) in query.items()])

    if query_string:
        return " where " + query_string
    return ""

#      _ _     _
#   __| (_)___| |__
#  / _` | / __| '_ \
# | (_| | \__ \ | | |
#  \__,_|_|___/_| |_|

def dish_validate_query(query_params):
    valid_dish_queries = ['name', 'simple_name', 'id', 'author']
    for k in list(query_params.keys()):
        if k not in valid_dish_queries:
            query_params.pop(k)

def dish_lookup(query_params):
    dish_validate_query(query_params)

    # Transform a name query into a simple name search
    if query_params.get('name'):
        query_params['simple_name'] = helpers.simplify(query_params.pop('name'))

    status, results, error = db_query("SELECT id, name FROM dishes", query_params, search=True)

    data = [{'id': _id, 'name': name} for (_id, name) in results]

    return status, data, error

def dish_put(dish):
    status, error = db_execute("INSERT INTO dishes VALUES (?, ?, ?, ?, ?)", (dish.id,
                                                                             dish.name,
                                                                             dish.simple_name,
                                                                             dish.author,
                                                                             dish.directions))

    return status, error

def dish_delete(dish_id):
    query = "DELETE FROM dishes"
    match = {'id': dish_id}
    param = "PRAGMA foreign_keys = 1"
    status, _, error = db_query(query, match, params=param)
    return status, error

def dish_get(query_params):
    dish_validate_query(query_params)
    status, results, error = db_query("SELECT * FROM dishes", query_params)

    data = []
    for (_id, name, _, author, directions) in results:
        data.append({'id': _id,
                     'name': name,
                     'author': author,
                     'directions': directions})

    return status, data, error

def dish_tag(dish_id, label_id):
    return db_execute("INSERT INTO tags VALUES(?, ?)", (dish_id, label_id))

def dish_untag(dish_id, label_id):
    query = "DELETE FROM tags"
    match = {'label_id': label_id, 'dish_id': dish_id}
    param = "PRAGMA foreign_keys = 1"
    status, _, error = db_query(query, match, params=param)
    return status, error

#      _                           _                 _
#   __| | ___ _ __   ___ _ __   __| | ___ _ __   ___(_) ___  ___
#  / _` |/ _ \ '_ \ / _ \ '_ \ / _` |/ _ \ '_ \ / __| |/ _ \/ __|
# | (_| |  __/ |_) |  __/ | | | (_| |  __/ | | | (__| |  __/\__ \
#  \__,_|\___| .__/ \___|_| |_|\__,_|\___|_| |_|\___|_|\___||___/
#            |_|

def dish_link(dependent_id, requisite_id):
    query = "INSERT INTO dependencies VALUES (?, ?)"
    values = (requisite_id, dependent_id)
    return db_execute(query, values)

def dish_unlink(dependent_id, requisite_id):
    query = "DELETE FROM dependencies"
    match = {'required_by': dependent_id, 'requisite': requisite_id}
    status, _, error = db_query(query, match)
    return status, error

def dish_requires(dish_id):
    query = "SELECT id, name FROM dishes JOIN dependencies ON dishes.id = dependencies.requisite"
    status, results, error = db_query(query, {'required_by': dish_id})
    data = [{'id': _id, 'name': name} for (_id, name) in results]
    return status, data, error

#  _                          _ _            _
# (_)_ __   __ _ _ __ ___  __| (_) ___ _ __ | |_
# | | '_ \ / _` | '__/ _ \/ _` | |/ _ \ '_ \| __|
# | | | | | (_| | | |  __/ (_| | |  __/ | | | |_
# |_|_| |_|\__, |_|  \___|\__,_|_|\___|_| |_|\__|
#          |___/

def ingredient_validate_query(query_params):
    valid_ingredient_queries = ['name', 'id']
    for key in list(query_params.keys()):
        if key not in valid_ingredient_queries:
            query_params.pop(key)

def ingredient_lookup(args):
    ingredient_validate_query(args)
    status, results, error = db_query("SELECT id, name FROM ingredients", args, search=True)

    data = [{'id': _id, 'name': name} for (_id, name) in results]

    return status, data, error

def ingredient_get(query_params):
    ingredient_validate_query(query_params)
    status, results, error = db_query("SELECT id, name FROM ingredients", query_params)

    data = [{'id': _id, 'name': name} for (_id, name) in results]

    return status, data, error

def ingredient_put(ingredient):
    return db_execute("INSERT INTO ingredients VALUES (?, ?)", (ingredient.id, ingredient.name))

def ingredient_delete(ingredient_id):
    query = "DELETE FROM ingredients"
    match = {'id': ingredient_id}
    param = "PRAGMA foreign_keys = 1"
    status, _, error = db_query(query, match, params=param)

    return status, error

#                       _                               _
#  _ __ ___  __ _ _   _(_)_ __ ___ _ __ ___   ___ _ __ | |_
# | '__/ _ \/ _` | | | | | '__/ _ \ '_ ` _ \ / _ \ '_ \| __|
# | | |  __/ (_| | |_| | | | |  __/ | | | | |  __/ | | | |_
# |_|  \___|\__, |\__,_|_|_|  \___|_| |_| |_|\___|_| |_|\__|
#              |_|

def requirement_get(query_params):
    status, results, error = db_query("SELECT * FROM requirements", query_params)
    data = []

    for (dish_id, ingredient_id, quantity) in results:
        data.append({'dish_id': dish_id,
                     'ingredient_id': ingredient_id,
                     'quantity': quantity})

    return status, data, error

def requirement_exists(query_params):
    _, results, _ = db_query("SELECT COUNT(*) FROM requirements", query_params)
    return results[0][0]

def requirement_put(requirement):
    query = "INSERT INTO requirements VALUES (?, ?, ?)"
    values = (requirement['dish_id'], requirement['ingredient_id'], requirement['quantity'])
    status, error = db_execute(query, values)
    data = {'id': requirement['ingredient_id'], 'quantity': requirement['quantity']}
    return status, data, error

def requirement_update(query, values):
    vals = ",".join(["{}='{}'".format(key, val) for (key, val) in values.items()])
    return db_execute("UPDATE requirements SET {} {}".format(vals, db_translate_dict(query)))

def requirement_delete(query):
    return db_query("DELETE FROM requirements", query)

#  _
# | |_ __ _  __ _ ___
# | __/ _` |/ _` / __|
# | || (_| | (_| \__ \
#  \__\__,_|\__, |___/
#           |___/

def tag_validate_query(query_params):
    valid_tag_queries = ['dish_id', 'label_id']
    for key in list(query_params.keys()):
        if key not in valid_tag_queries:
            query_params.pop(key)

def tag_get(query_params):
    tag_validate_query(query_params)
    query_str = "SELECT id, name FROM labels JOIN tags ON tags.label_id = labels.id"
    status, results, error = db_query(query_str, query_params, search=True)
    data = [{'name': name, 'id': _id} for (_id, name) in results]
    return status, data, error

def tag_show(tag_id):
    query = "SELECT dishes.id, dishes.name FROM dishes JOIN tags ON dishes.id = tags.dish_id"
    status, results, error = db_query(query, {'label_id': tag_id})
    data = [{'name': name, 'id': _id} for (_id, name) in results]
    return status, data, error

#  _       _          _
# | | __ _| |__   ___| |___
# | |/ _` | '_ \ / _ \ / __|
# | | (_| | |_) |  __/ \__ \
# |_|\__,_|_.__/ \___|_|___/

def label_validate_query(query_params):
    valid_label_queries = ['name', 'id']
    for key in list(query_params.keys()):
        if key not in valid_label_queries:
            query_params.pop(key)

def label_get(query_params):
    label_validate_query(query_params)
    query_str = "SELECT id, name FROM labels"
    status, results, error = db_query(query_str, query_params, search=True)
    data = [{'name': name, 'id': _id} for (_id, name) in results]
    return status, data, error

def label_put(label_name):
    _id = helpers.hash256(label_name)
    simple_name = helpers.simplify(label_name)
    query = "INSERT INTO labels VALUES (?, ?, ?)"
    values = (_id, label_name, simple_name)
    status, error = db_execute(query, values)
    return status, {'id': _id, 'name': label_name}, error

def label_delete(label_id):
    query = "DELETE FROM labels"
    match = {'id': label_id}
    param = "PRAGMA foreign_keys = 1"
    status, _, error = db_query(query, match, params=param)
    return status, error

if __name__ == "__main__":
    db_drop_tables(['dishes', 'ingredients', 'requirements', 'dependencies', 'labels', 'tags'])
    db_execute(TAGS)
    db_execute(LABELS)
    db_execute(DISHES)
    db_execute(INGREDIENTS)
    db_execute(REQUIREMENTS)
    db_execute(DEPENDENCIES)
