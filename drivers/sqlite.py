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
    print((template, values))

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
    operator = " LIKE " if search else "="

    if search:
        for (k, v) in query_params.items():
            query_params[k] = "%{}%".format(v)

    if len(query_params) > 0:
        query_string = query_string + " WHERE " + " AND ".join(["{}{}:{}".format(key, operator, key) for (key, _) in query_params.items()])

    try:
        print((query_string, query_params))
        CURSOR.execute(query_string, query_params)
        status = True
        data = CURSOR.fetchall()
        error = None
    except sqlite3.IntegrityError as err:
        status = False
        data = []
        error = str(err)

    db_close(CONNEXION)
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

valid_dish_queries = ['name', 'simple_name', 'id', 'author']

def dish_validate_query(query_params):
    [query_params.pop(k) for k in list(query_params.keys()) if k not in valid_dish_queries]

def dish_lookup(query_params):
    dish_validate_query(query_params)

    # Transform a name query into a simple name search
    if query_params.get('name'):
        query_params['simple_name'] = helpers.simplify(query_params.pop('name'))

    status, results, error = db_query("SELECT id, name FROM dishes", query_params, search=True)
    data = []

    for (_id, name) in results:
        data.append({'id': _id,
                    'name': name})

    return data

def dish_put(dish):
    status, error = db_execute("INSERT INTO dishes VALUES (?, ?, ?, ?, ?)", (dish.id,
        dish.name,
        dish.simple_name,
        dish.author,
        dish.directions))

    return status, error

def dish_delete(query_params):
    dish_validate_query(query_params)
    return db_execute("DELETE FROM dishes {}".format(db_translate_dict(query_params)), params="PRAGMA foreign_keys = 1")

def dish_get(query_params):
    dish_validate_query(query_params)
    status, results, error = db_query("SELECT * FROM dishes", query_params)
    data = []

    for (_id, name, simple_name, author, directions) in results:
        status, requirements_data, error = db_query("SELECT name, quantity FROM ingredients JOIN requirements ON id = ingredient_id WHERE dish_id = '{}'".format(_id))
        status, dependencies_data, error = db_query("SELECT id, name FROM dependencies JOIN dishes ON requisite = id WHERE required_by = '{}'".format(_id))
        status, tags_data, error = db_query("SELECT labels.id, labels.name FROM labels JOIN tags ON labels.id = label_id WHERE dish_id = '{}'".format(_id))

        requirements = [{'ingredient': name, 'quantity': quantity} for (name, quantity) in requirements_data]
        dependencies = [{'id': _id, 'name': name} for (_id, name) in dependencies_data]
        tags = [{'id': _id, 'name': name} for (_id, name) in tags_data]

        data.append({'id': _id,
                 'tags': tags,
                 'name': name,
                 'author': author,
                 'directions': directions,
                 'ingredients': requirements,
                 'dependencies': dependencies})

    return data

#  _                          _ _            _   
# (_)_ __   __ _ _ __ ___  __| (_) ___ _ __ | |_ 
# | | '_ \ / _` | '__/ _ \/ _` | |/ _ \ '_ \| __|
# | | | | | (_| | | |  __/ (_| | |  __/ | | | |_ 
# |_|_| |_|\__, |_|  \___|\__,_|_|\___|_| |_|\__|
#          |___/                                 

valid_ingredient_queries = ['name', 'id']

def ingredient_validate_query(query_params):
    [query_params.pop(k) for k in list(query_params.keys()) if k not in valid_ingredient_queries]

def ingredient_lookup(args):
    ingredient_validate_query(args)
    status, results, error = db_query("SELECT id, name FROM ingredients", args, search=True)

    data = [{'id': _id, 'name': name} for (_id, name) in results]

    return True, data, None

def ingredient_get(query_params):
    ingredient_validate_query(query_params)
    status, results, error = db_query("SELECT id, name FROM ingredients", query_params)

    data = [{'id': _id, 'name': name} for (_id, name) in results]

    return status, data, error

def ingredient_put(ingredient):
    return db_execute("INSERT INTO ingredients VALUES (?, ?)", (ingredient.id, ingredient.name))

def ingredient_delete(ingredient_id):
    status, ingredient, error = db_query("DELETE FROM ingredients", {'id': ingredient_id}, params="PRAGMA foreign_keys = 1")
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
    status, results, error = db_query("SELECT COUNT(*) FROM requirements", query_params)
    return results[0][0]

def requirement_put(requirement):
    status, error = db_execute("INSERT INTO requirements VALUES (?, ?, ?)", (requirement['dish_id'], requirement['ingredient_id'], requirement['quantity']))
    return status, {'id': requirement['ingredient_id'], 'quantity': requirement['quantity']}, error

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

def label_get(stub = ""):
    status, results, error = db_query("SELECT id, name FROM labels", {'simple_name': stub}, search=True)
    data = []
    for (_id, name) in results:
        data.append({'name': name, 'id': _id})
    return data

def label_put(label_name):
    _id = helpers.hash256(label_name)
    simple_name = helpers.simplify(label_name)
    status, error = db_execute("INSERT INTO labels VALUES (?, ?, ?)", (_id, label_name, simple_name))
    return status, {'id': _id, 'name': label_name}, error

def tag(dish_id, tag_id):
    return db_execute("INSERT INTO tags VALUES(?, ?)", (dish_id, tag_id))

def label_show(tag_id):
    status, results, error = db_query("SELECT dishes.id, dishes.name FROM dishes JOIN tags ON dishes.id = tags.dish_id", {'label_id': tag_id})
    return True, results, ""

if __name__ == "__main__":
    db_drop_tables(['dishes', 'ingredients', 'requirements', 'dependencies', 'labels', 'tags'])
    db_execute(TAGS)
    db_execute(LABELS)
    db_execute(DISHES)
    db_execute(INGREDIENTS)
    db_execute(REQUIREMENTS)
    db_execute(DEPENDENCIES)
