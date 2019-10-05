import sqlite3

DBPATH='/var/lib/knife/database.db'

DISHES='''
CREATE TABLE dishes (
    id TEXT,
    name TEXT NOT NULL,
    author TEXT,
    desc TEXT,
    PRIMARY KEY (id))
'''

INGREDIENTS='''
CREATE TABLE ingredients (
    id text primary key, 
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

#      _       _        _                    
#   __| | __ _| |_ __ _| |__   __ _ ___  ___ 
#  / _` |/ _` | __/ _` | '_ \ / _` / __|/ _ \
# | (_| | (_| | || (_| | |_) | (_| \__ \  __/
#  \__,_|\__,_|\__\__,_|_.__/ \__,_|___/\___|

def setup(params=None):
    CONNEXION = sqlite3.connect(DBPATH)
    if params:
        CONNEXION.execute(params)
    CURSOR = CONNEXION.cursor()

    return CONNEXION, CURSOR

def close(connexion):
    connexion.commit()
    connexion.close()

def execute(query_string, params=None):
    CONNEXION, CURSOR = setup(params)

    try:
        CURSOR.execute(query_string)
        status = True
    except sqlite3.IntegrityError as err:
        status = False

    close(CONNEXION)
    return status

def query(query_string, params=None):
    CONNEXION, CURSOR = setup(params)

    try:
        CURSOR.execute(query_string)
        data = CURSOR.fetchall()
    except sqlite3.IntegrityError as err:
        data = []

    close(CONNEXION)
    return data

def drop_tables(tables):
    for name in tables:
        try:
            execute("DROP TABLE {}".format(name))
        except Exception as err:
            print("Error {}".format(err))
            None

def translate_dict(query):
    query_string = " and ".join(["{}='{}'".format(key, val) for (key, val) in query.items()])

    if query_string:
        return " where " + query_string
    return ""


def setup_database():
    drop_tables(['dishes', 'ingredients', 'requirements'])
    execute(DISHES)
    execute(INGREDIENTS)
    execute(REQUIREMENTS)

#      _ _     _     
#   __| (_)___| |__  
#  / _` | / __| '_ \ 
# | (_| | \__ \ | | |
#  \__,_|_|___/_| |_|

def put_dish(dish):
    return execute("INSERT INTO dishes VALUES ('{}', '{}', '{}', '{}')".format(dish.id, dish.name, 'jb', dish.directions))

def delete_dish(query_params):
    return execute("delete from dishes {}".format(translate_dict(query_params)), params="PRAGMA foreign_keys = 1")

def get_dish(query_params):
    results = query("select * from dishes {}".format(translate_dict(query_params)))
    data = []

    for (_id, name, author, directions) in results:
        requirements_data = query("select name, quantity from ingredients join requirements on id = ingredient_id where dish_id = '{}'".format(_id))
        requirements = [{'name': name, 'quantity': quantity} for (name, quantity) in requirements_data]
        data.append({'_id': _id,
                 'name': name,
                 'author': author,
                 'directions': directions,
                 'ingredients': requirements})
    return data

#  _                          _ _            _   
# (_)_ __   __ _ _ __ ___  __| (_) ___ _ __ | |_ 
# | | '_ \ / _` | '__/ _ \/ _` | |/ _ \ '_ \| __|
# | | | | | (_| | | |  __/ (_| | |  __/ | | | |_ 
# |_|_| |_|\__, |_|  \___|\__,_|_|\___|_| |_|\__|
#          |___/                                 

def get_ingredient(query_params):
    results = query("select * from ingredients {}".format(translate_dict(query_params)))
    data = []

    for (_id, name) in results:
        data.append({'_id': _id,
                 'name': name})
    return data

def put_ingredient(ingredient):
    return execute("INSERT INTO ingredients VALUES ('{}', '{}')".format(ingredient.id, ingredient.name))

#                       _                               _   
#  _ __ ___  __ _ _   _(_)_ __ ___ _ __ ___   ___ _ __ | |_ 
# | '__/ _ \/ _` | | | | | '__/ _ \ '_ ` _ \ / _ \ '_ \| __|
# | | |  __/ (_| | |_| | | | |  __/ | | | | |  __/ | | | |_ 
# |_|  \___|\__, |\__,_|_|_|  \___|_| |_| |_|\___|_| |_|\__|
#              |_|                                          

def get_requirement(query_params):
    results = query("select * from requirements {}".format(translate_dict(query_params)))
    data = []

    for (dish_id, ingredient_id, quantity) in results:
        data.append({'dish_id': dish_id,
                     'ingredient_id': ingredient_id,
                     'quantity': quantity})
    return data

def exists_requirement(query_params):
    return len(get_requirement(query_params)) > 0

def put_requirement(requirement):
    return execute("INSERT INTO requirements VALUES ('{}', '{}', '{}')".format(requirement['dish_id'], requirement['ingredient_id'], requirement['quantity']))

def update_requirement(query, values):
    vals = ",".join(["{}='{}'".format(key, val) for (key, val) in values.items()])
    return execute("UPDATE requirements SET {} {}".format(vals, translate_dict(query)))

def delete_requirement(query):
    return execute("DELETE FROM requirements {}".format(translate_dict(query)))


if __name__ == "__main__":
    setup_database()
