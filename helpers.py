import hashlib
from unidecode import unidecode

def hash256(string):
    grounder = hashlib.sha256()
    grounder.update(string.encode())
    return grounder.hexdigest()

def simplify(string):
    return unidecode(string.lower()).replace(' ', '_').replace("'", '_')
