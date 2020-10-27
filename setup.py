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

setuptools.setup(name=NAME,
                 version=VERSION,
                 author=AUTHOR,
                 author_email=AUTHOR_EMAIL,
                 description=DESCRIPTION,
                 scripts=['scripts/knife'],
                 packages=list(PACKAGES.keys()),
                 package_dir=PACKAGES)
#cmdclass={'install': Install})
