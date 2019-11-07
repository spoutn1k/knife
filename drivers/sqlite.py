import sqlite3
import helpers

DBPATH='/var/lib/knife/database.db'

DISHES='''
CREATE TABLE dishes (
    id TEXT,
    name TEXT NOT NULL,
    simple_name TEXT,
    author TEXT,
    desc TEXT,
    PRIMARY KEY (id))
'''

DEPENDENCIES='''
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

INGREDIENTS='''
CREATE TABLE ingredients (
    id text PRIMARY KEY, 
    name text)
'''

REQUIREMENTS='''
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

LABELS='''
CREATE TABLE labels (
    id TEXT,
    name TEXT NOT NULL,
    simple_name TEXT,
    PRIMARY KEY (id))
'''

TAGS='''
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
    CONNEXION = sqlite3.connect(DBPATH)
    if params:
        CONNEXION.execute(params)
    CURSOR = CONNEXION.cursor()

    return CONNEXION, CURSOR

def db_close(connexion):
    connexion.commit()
    connexion.close()

def db_execute(template, values=None, params=None):
    CONNEXION, CURSOR = db_setup(params)

    try:
        if values:
            CURSOR.execute(template, values)
        else:
            CURSOR.execute(template)
        status = True
        error = None
    except sqlite3.IntegrityError as err:
        status = False
        error = repr(err)

    db_close(CONNEXION)
    return status, error

def db_query(query_string, query_params={}, params=None, search=False):
    """
    Query wrapper
    We assume all query params keys are sanitized
    """
    CONNEXION, CURSOR = db_setup(params)
    operator = " like " if search else "="

    if search:
        for (k, v) in query_params.items():
            query_params[k] = "%{}%".format(v)

    if len(query_params) > 0:
        query_string = query_string + " where " + " and ".join(["{}{}:{}".format(key, operator, key) for (key, _) in query_params.items()])

    try:
        CURSOR.execute(query_string, query_params)
        data = CURSOR.fetchall()
    except sqlite3.IntegrityError as err:
        data = []

    db_close(CONNEXION)
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

valid_dish_queries = ['name', 'simple_name', 'id', 'author']

def dish_validate_db_query(query_params):
    [query_params.pop(k) for k in list(query_params.keys()) if k not in valid_dish_queries]

def dish_put(dish):
    status, error = db_execute("INSERT INTO dishes VALUES (?, ?, ?, ?, ?)", (dish.id,
        dish.name,
        dish.simple_name,
        dish.author,
        dish.directions))
    for data in dish.requirements:
        if status:
            ingredient_put(data['ingredient'])
            status = status and requirement_put({'dish_id': dish.id,
                                                'ingredient_id': data['ingredient'].id,
                                                'quantity': data['quantity']})
    for data in dish.dependencies:
        if status and data.get('id'):
            status = status and db_execute("INSERT INTO dependencies VALUES (?, ?)", (data['id'], dish.id))

    return status, db_translate_exception(error)

def dish_delete(query_params):
    dish_validate_db_query(query_params)
    return db_execute("delete from dishes {}".format(db_translate_dict(query_params)), params="PRAGMA foreign_keys = 1")

def dish_get(query_params):
    dish_validate_db_query(query_params)
    results = db_query("select * from dishes", query_params)
    data = []

    for (_id, name, simple_name, author, directions) in results:
        requirements_data = db_query("select name, quantity from ingredients join requirements on id = ingredient_id where dish_id = '{}'".format(_id))
        dependencies_data = db_query("SELECT id, name FROM dependencies JOIN dishes on requisite = id where required_by = '{}'".format(_id))
        tags_data = db_query("SELECT labels.id, labels.name FROM labels JOIN tags on labels.id = label_id where dish_id = '{}'".format(_id))
        requirements = [{'ingredient': name, 'quantity': quantity} for (name, quantity) in requirements_data]
        dependencies = [{'id': _id, 'name': name} for (_id, name) in dependencies_data]
        tags = [{'id': _id, 'name': name} for (_id, name) in tags_data]

        data.append({'id': _id,
                 'name': name,
                 'author': author,
                 'directions': directions,
                 'ingredients': requirements,
                 'tags': tags,
                 'dependencies': dependencies})
    return data

def dish_lookup(query_params):
    dish_validate_db_query(query_params)
    results = db_query("select id, name from dishes", query_params, search=True)
    data = []

    for (_id, name) in results:
        data.append({'id': _id,
                    'name': name})

    return data

#  _                          _ _            _   
# (_)_ __   __ _ _ __ ___  __| (_) ___ _ __ | |_ 
# | | '_ \ / _` | '__/ _ \/ _` | |/ _ \ '_ \| __|
# | | | | | (_| | | |  __/ (_| | |  __/ | | | |_ 
# |_|_| |_|\__, |_|  \___|\__,_|_|\___|_| |_|\__|
#          |___/                                 

valid_ingredient_queries = ['name', 'id']

def ingredient_validate_db_query(query_params):
    [query_params.pop(k) for k in list(query_params.keys()) if k not in valid_ingredient_queries]

def ingredient_get(query_params):
    ingredient_validate_db_query(query_params)
    results = db_query("select * from ingredients", query_params)
    data = []

    for (_id, name) in results:
        data.append({'id': _id,
                 'name': name})
    return data

def ingredient_put(ingredient):
    return db_execute("INSERT INTO ingredients VALUES (?, ?)", (ingredient.id, ingredient.name))

#                       _                               _   
#  _ __ ___  __ _ _   _(_)_ __ ___ _ __ ___   ___ _ __ | |_ 
# | '__/ _ \/ _` | | | | | '__/ _ \ '_ ` _ \ / _ \ '_ \| __|
# | | |  __/ (_| | |_| | | | |  __/ | | | | |  __/ | | | |_ 
# |_|  \___|\__, |\__,_|_|_|  \___|_| |_| |_|\___|_| |_|\__|
#              |_|                                          

def requirement_get(query_params):
    results = db_query("select * from requirements", query_params)
    data = []

    for (dish_id, ingredient_id, quantity) in results:
        data.append({'dish_id': dish_id,
                     'ingredient_id': ingredient_id,
                     'quantity': quantity})
    return data

def requirement_exists(query_params):
    return len(requirement_get(query_params)) > 0

def requirement_put(requirement):
    return db_execute("INSERT INTO requirements VALUES (?, ?, ?)", (requirement['dish_id'], requirement['ingredient_id'], requirement['quantity']))

def requirement_update(query, values):
    vals = ",".join(["{}='{}'".format(key, val) for (key, val) in values.items()])
    return db_execute("UPDATE requirements SET {} {}".format(vals, db_translate_dict(query)))

def requirement_delete(query):
    return db_execute("DELETE FROM requirements {}".format(db_translate_dict(query)))

#  _                  
# | |_ __ _  __ _ ___ 
# | __/ _` |/ _` / __|
# | || (_| | (_| \__ \
#  \__\__,_|\__, |___/
#           |___/     

def label_get(stub = ""):
    results = db_query("select id, name from labels", {'simple_name': stub}, search=True)
    data = []
    for (_id, name) in results:
        data.append({'name': name, 'id': _id})
    return data

def label_put(label_name):
    return db_execute("INSERT INTO labels VALUES (?, ?, ?)", (helpers.hash256(label_name), label_name, helpers.simplify(label_name)))

def db_translate_exception(err):
    if str(err) == "IntegrityError('UNIQUE constraint failed: dishes.id')":
        return "Dish already exists"
    else:
        return repr(err)

if __name__ == "__main__":
    db_drop_tables(['dishes', 'ingredients', 'requirements', 'dependencies', 'labels', 'tags'])
    db_execute(DISHES)
    db_execute(INGREDIENTS)
    db_execute(REQUIREMENTS)
    db_execute(DEPENDENCIES)
    db_execute(LABELS)
    db_execute(TAGS)

