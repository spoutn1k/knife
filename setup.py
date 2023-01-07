import setuptools

NAME = 'knife'
AUTHOR = 'Jean-Baptiste Skutnik'
AUTHOR_EMAIL = 'jb.skutnik@gmail.com'
DESCRIPTION = 'Recipe manager'
VERSION = "0.3"

MODULES = ["knife", "knife.models", "knife.drivers"]
PACKAGES = {}
for name in MODULES:
    PACKAGES[name] = name.replace(".", "/")

DEPENDENCIES = []
DEPENDENCY_FILE_PATH = "./requirements.txt"

try:
    with open(DEPENDENCY_FILE_PATH, 'r') as dependency_file:
        DEPENDENCIES = dependency_file.readlines()
except Exception as err:
    print(
        f"Failed to lookup dependencies from {DEPENDENCY_FILE_PATH}: {str(err)}",
        file=sys.stderr)

setuptools.setup(name=NAME,
                 version=VERSION,
                 author=AUTHOR,
                 author_email=AUTHOR_EMAIL,
                 description=DESCRIPTION,
                 scripts=['scripts/knife'],
                 install_requires=DEPENDENCIES,
                 packages=list(PACKAGES.keys()),
                 package_dir=PACKAGES)
#cmdclass={'install': Install})
