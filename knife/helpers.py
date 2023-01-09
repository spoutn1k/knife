import hashlib
from unidecode import unidecode


def fix_args(dictionnary):
    """
    This code exists because python changed the way it translated
    dictionnaries between versions. When request.args was processed to be used
    later in the code, lists were created in 3.5 and not in 3.7.
    This function fixes that by parsing the dictionnary first
    """
    for (key, value) in dictionnary.items():
        if isinstance(value, list):
            dictionnary[key] = value[0]
    return dictionnary


def hash256(string):
    grinder = hashlib.sha256()
    grinder.update(string.encode())
    return grinder.hexdigest()


def simplify(string):
    return unidecode(string.lower()).replace(' ', '_').replace("'", '_')
