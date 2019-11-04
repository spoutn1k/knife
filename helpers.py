from unidecode import unidecode
import hashlib

def hash256(string):
    m = hashlib.sha256()
    m.update(string.encode())
    return m.hexdigest()

def simplify(string):
    return unidecode(string.lower()).replace(' ', '_').replace("'", '_')

