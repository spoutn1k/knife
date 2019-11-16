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
    directions TEXT,
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
    id TEXT,
    name TEXT NOT NULL,
    simple_name TEXT,
    PRIMARY KEY (id))
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

def db_execute(template, values={}, params=None):
    connexion, cursor = db_setup(params)

    log(template, values)
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
        keys = ["{}{}:{}".format(key, operator, key) for (key, _) in query_params.items()]
        query_string = query_string + " WHERE " + " AND ".join(keys)

    log(query_string, query_params)
    try:
        cursor.execute(query_string, query_params)
        data = cursor.fetchall()
    finally:
        db_close(connexion)

    return data

def db_update(table, updated_vals={}, matching_vals={}, params=None, match=False):
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
        replace = ["{}{}:{}".format(key, '=', key) for (key, _) in updated_vals.items()]
        match = ["{}{}:{}_match".format(key, operator, key) for (key, _) in matching_vals.items()]
        query_string = "UPDATE {} SET {} WHERE {}".format(table, ','.join(replace), ' AND '.join(match))

    for (key, value) in matching_vals.items():
        updated_vals["{}_match".format(key)] = value
    log(query_string, updated_vals)
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
    query_string = " and ".join(["{}='{}'".format(key, val) for (key, val) in query.items()])

    if query_string:
        return " where " + query_string
    return ""

#      _ _     _
#   __| (_)___| |__
#  / _` | / __| '_ \
# | (_| | \__ \ | | |
#  \__,_|_|___/_| |_|

def dish_lookup(query_params, match=True):
    results = db_query("SELECT id, name FROM dishes", query_params, match=match)
    return [{'id': _id, 'name': name} for (_id, name) in results]

def dish_put(dish):
    db_execute("INSERT INTO dishes VALUES (?, ?, ?, ?, ?)", (dish.id,
                                                             dish.name,
                                                             dish.simple_name,
                                                             dish.author,
                                                             dish.directions))

def dish_delete(dish_id):
    query = "DELETE FROM dishes"
    match = {'id': dish_id}
    params = "PRAGMA foreign_keys = 1"
    db_query(query, match, params)

def dish_get(query_params):
    results = db_query("SELECT * FROM dishes", query_params)

    data = []
    for (_id, name, _, author, directions) in results:
        data.append({'id': _id,
                     'name': name,
                     'author': author,
                     'directions': directions})
    return data

def dish_update(dish_id, dish_data):
    db_update('dishes', dish_data, {'id': dish_id})

def dish_tag(dish_id, label_id):
    return db_execute("INSERT INTO tags VALUES(?, ?)", (dish_id, label_id))

def dish_untag(dish_id, label_id):
    query = "DELETE FROM tags"
    match = {'label_id': label_id, 'dish_id': dish_id}
    params = "PRAGMA foreign_keys = 1"
    db_query(query, match, params)

#      _                           _                 _
#   __| | ___ _ __   ___ _ __   __| | ___ _ __   ___(_) ___  ___
#  / _` |/ _ \ '_ \ / _ \ '_ \ / _` |/ _ \ '_ \ / __| |/ _ \/ __|
# | (_| |  __/ |_) |  __/ | | | (_| |  __/ | | | (__| |  __/\__ \
#  \__,_|\___| .__/ \___|_| |_|\__,_|\___|_| |_|\___|_|\___||___/
#            |_|

def dish_link(dependent_id, requisite_id):
    query = "INSERT INTO dependencies VALUES (?, ?)"
    values = (requisite_id, dependent_id)
    db_execute(query, values)

def dish_unlink(dependent_id, requisite_id):
    query = "DELETE FROM dependencies"
    match = {'required_by': dependent_id, 'requisite': requisite_id}
    db_query(query, match)

def dish_requires(dish_id):
    query = "SELECT id, name FROM dishes JOIN dependencies ON dishes.id = dependencies.requisite"
    results = db_query(query, {'required_by': dish_id})
    return [{'id': _id, 'name': name} for (_id, name) in results]

#  _                          _ _            _
# (_)_ __   __ _ _ __ ___  __| (_) ___ _ __ | |_
# | | '_ \ / _` | '__/ _ \/ _` | |/ _ \ '_ \| __|
# | | | | | (_| | | |  __/ (_| | |  __/ | | | |_
# |_|_| |_|\__, |_|  \___|\__,_|_|\___|_| |_|\__|
#          |___/

def ingredient_get(args, match=False):
    results = db_query("SELECT id, name FROM ingredients", args, match=match)

    return [{'id': _id, 'name': name} for (_id, name) in results]

def ingredient_put(ingredient):
    db_execute("INSERT INTO ingredients VALUES (?, ?, ?)", (ingredient.id, ingredient.name, ingredient.simple_name))

def ingredient_delete(ingredient_id):
    query = "DELETE FROM ingredients"
    match = {'id': ingredient_id}
    params = "PRAGMA foreign_keys = 1"
    db_query(query, match, params)

def ingredient_update(ingredient_id, ingredient_data):
    db_update('ingredients', ingredient_data, {'id': ingredient_id})

#                       _                               _
#  _ __ ___  __ _ _   _(_)_ __ ___ _ __ ___   ___ _ __ | |_
# | '__/ _ \/ _` | | | | | '__/ _ \ '_ ` _ \ / _ \ '_ \| __|
# | | |  __/ (_| | |_| | | | |  __/ | | | | |  __/ | | | |_
# |_|  \___|\__, |\__,_|_|_|  \___|_| |_| |_|\___|_| |_|\__|
#              |_|

def requirement_get(query_params):
    results = db_query("SELECT * FROM requirements", query_params)
    data = []

    for (dish_id, ingredient_id, quantity) in results:
        data.append({'dish_id': dish_id,
                     'ingredient_id': ingredient_id,
                     'quantity': quantity})
    return data

def requirement_exists(query_params):
    results = db_query("SELECT COUNT(*) FROM requirements", query_params)
    return results[0][0]

def requirement_put(requirement):
    query = "INSERT INTO requirements VALUES (?, ?, ?)"
    values = (requirement['dish_id'], requirement['ingredient_id'], requirement['quantity'])
    db_execute(query, values)
    data = {'id': requirement['ingredient_id'], 'quantity': requirement['quantity']}
    return data

def requirement_update(query, values):
    return db_update('requirements', values, query)

def requirement_delete(query):
    return db_query("DELETE FROM requirements", query)

#  _
# | |_ __ _  __ _ ___
# | __/ _` |/ _` / __|
# | || (_| | (_| \__ \
#  \__\__,_|\__, |___/
#           |___/

def tag_get(query_params, match=False):
    query_str = "SELECT id, name FROM labels JOIN tags ON tags.label_id = labels.id"
    results = db_query(query_str, query_params, match)
    data = [{'name': name, 'id': _id} for (_id, name) in results]
    return data

def tag_show(tag_id):
    query = "SELECT dishes.id, dishes.name FROM dishes JOIN tags ON dishes.id = tags.dish_id"
    results = db_query(query, {'label_id': tag_id})
    data = [{'name': name, 'id': _id} for (_id, name) in results]
    return data

#  _       _          _
# | | __ _| |__   ___| |___
# | |/ _` | '_ \ / _ \ / __|
# | | (_| | |_) |  __/ \__ \
# |_|\__,_|_.__/ \___|_|___/

def label_get(query_params, match=False):
    query_str = "SELECT id, name FROM labels"
    results = db_query(query_str, query_params, match)
    return [{'name': name, 'id': _id} for (_id, name) in results]

def label_put(label):
    query = "INSERT INTO labels VALUES (?, ?, ?)"
    values = (label.id, label.name, label.simple_name)
    db_execute(query, values)

def label_delete(label_id):
    query = "DELETE FROM labels"
    match = {'id': label_id}
    params = "PRAGMA foreign_keys = 1"
    db_query(query, match, params)

def label_update(label_id, label_data):
    db_update('labels', label_data, {'id': label_id})

if __name__ == "__main__":
    db_drop_tables(['dishes', 'ingredients', 'requirements', 'dependencies', 'labels', 'tags'])
    db_execute(TAGS)
    db_execute(LABELS)
    db_execute(DISHES)
    db_execute(INGREDIENTS)
    db_execute(REQUIREMENTS)
    db_execute(DEPENDENCIES)
