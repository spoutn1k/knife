from pathlib import Path
from knife.store import Store
from knife.models import Recipe, Dependency
from knife.models.knife_model import Field
from knife.drivers.json import JSONDriver
from test import TestCase
from tempfile import NamedTemporaryFile


class TestDriverJSONRead(TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def setUp(self):
        json = """{
    "recipes": {
        "1": {
            "id": "7fa1f29e27a48cc8dc73cbdcdec7231ff4923bd1520fc8e6e3413547172d490d",
            "name": "Fajitas",
            "simple_name": "fajitas",
            "author": "",
            "directions": "",
            "information": ""
        },
        "2": {
            "id": "06faab5fe9048cf9a5d009952e3e491fb4b785cf38a6230f450167004f3733ed",
            "name": "Guacamole",
            "simple_name": "guacamole",
            "author": "",
            "directions": "",
            "information": ""
        },
        "3": {
            "id": "8a69388e1a2c4c6f766f5f5c7e2f8d578789c4fb11e32de0b808658b4eea32d9",
            "name": "Pico de Gallo",
            "simple_name": "pico_de_gallo",
            "author": "",
            "directions": "",
            "information": ""
        },
        "4": {
            "id": "4e020bbbd8f2dbfab1a3b3d768dc141b036c26342e5cc4ea966cdae168455b0e",
            "name": "Chipotle Chicken",
            "simple_name": "chipotle_chicken",
            "author": "",
            "directions": "",
            "information": ""
        },
        "5": {
            "id": "5e020bbbd8f2dbfab1a3b3d768dc141b036c26342e5cc4ea966cdae168455b0e",
            "name": "Chipotle Chicken Jaliscan",
            "simple_name": "chipotle_chicken_jaliscan",
            "author": "",
            "directions": "",
            "information": ""
        }
    },
    "dependencies": {
        "1": {
            "required_by": "7fa1f29e27a48cc8dc73cbdcdec7231ff4923bd1520fc8e6e3413547172d490d",
            "requisite": "06faab5fe9048cf9a5d009952e3e491fb4b785cf38a6230f450167004f3733ed",
            "quantity": "",
            "optional": false
        },
        "2": {
            "required_by": "7fa1f29e27a48cc8dc73cbdcdec7231ff4923bd1520fc8e6e3413547172d490d",
            "requisite": "4e020bbbd8f2dbfab1a3b3d768dc141b036c26342e5cc4ea966cdae168455b0e",
            "quantity": "",
            "optional": false
        },
        "3": {
            "required_by": "06faab5fe9048cf9a5d009952e3e491fb4b785cf38a6230f450167004f3733ed",
            "requisite": "8a69388e1a2c4c6f766f5f5c7e2f8d578789c4fb11e32de0b808658b4eea32d9",
            "quantity": "",
            "optional": false
        }
    }
}
"""
        with NamedTemporaryFile(mode='w',
                                encoding='utf-8',
                                delete=False,
                                suffix='.json') as temp:
            self.datafile = temp
            self.datafile.write(json)

        self.driver = JSONDriver(self.datafile.name)

    def tearDown(self):
        self.datafile.close()
        self.driver.db.close()
        Path(self.datafile.name).unlink()

    def test_read_model(self):
        dump = self.driver.read(Recipe)

        self.assertEqual(len(dump), 5)
        self.assertSetEqual(set(dump[0].keys()), set(Recipe.fields.fields))

        names = set(
            filter(None, map(lambda x: x.get(Recipe.fields.name), dump)))
        self.assertSetEqual(
            names, {
                'Fajitas',
                'Guacamole',
                'Pico de Gallo',
                'Chipotle Chicken',
                'Chipotle Chicken Jaliscan',
            })

    def test_read_model_filtered(self):
        dump = self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.name: 'Fajitas'
                                }])

        self.assertEqual(len(dump), 1)
        self.assertSetEqual(set(dump[0].keys()), set(Recipe.fields.fields))

        names = set(
            filter(None, map(lambda x: x.get(Recipe.fields.name), dump)))
        self.assertSetEqual(names, {'Fajitas'})

    def test_read_model_filtered_exact(self):
        dump = self.driver.read(Recipe, filters=[{Recipe.fields.name: 'ji'}])
        self.assertEqual(len(dump), 0)

        dump = self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.name: 'ji'
                                }],
                                exact=False)
        names = set(
            filter(None, map(lambda x: x.get(Recipe.fields.name), dump)))
        self.assertSetEqual(names, {'Fajitas'})

        dump = self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.simple_name:
                                    'chipotle_chicken'
                                }],
                                exact=False)
        self.assertEqual(len(dump), 2)
        names = set(
            filter(None, map(lambda x: x.get(Recipe.fields.name), dump)))
        self.assertSetEqual(names,
                            {'Chipotle Chicken', 'Chipotle Chicken Jaliscan'})

        dump = self.driver.read(Recipe,
                                filters=[{
                                    Recipe.fields.simple_name:
                                    'chipotle_chicken'
                                }],
                                exact=True)
        self.assertEqual(len(dump), 1)
        names = set(
            filter(None, map(lambda x: x.get(Recipe.fields.name), dump)))
        self.assertSetEqual(names, {'Chipotle Chicken'})

    def test_read_model_columns(self):
        dump = self.driver.read(Recipe, columns=['*'])

        self.assertEqual(len(dump), 5)
        self.assertSetEqual(set(dump[0].keys()), set(Recipe.fields.fields))

        columns = {Recipe.fields.name, Recipe.fields.author}
        dump = self.driver.read(Recipe, columns=columns)
        self.assertSetEqual(set(dump[0].keys()), columns)

    def test_read_join_model(self):
        dump = self.driver.read((
            Dependency,
            Recipe,
            Dependency.fields.required_by,
            Recipe.fields.id,
        ))

        self.assertEqual(len(dump), 3)
        self.assertSetEqual(
            set(dump[0].keys()),
            set(Recipe.fields.fields) | set(Dependency.fields.fields))

        names = set(filter(None, map(lambda x: x.get('name'), dump)))
        self.assertNotIn('Pico de Gallo', names)

    def test_read_join_model_filtered(self):
        fajitas_id = '7fa1f29e27a48cc8dc73cbdcdec7231ff4923bd1520fc8e6e3413547172d490d'
        dump = self.driver.read(
            (
                Dependency,
                Recipe,
                Dependency.fields.required_by,
                Recipe.fields.id,
            ),
            filters=[{
                Dependency.fields.required_by: fajitas_id
            }],
        )

        self.assertEqual(len(dump), 2)
        self.assertSetEqual(
            set(dump[0].keys()),
            set(Recipe.fields.fields) | set(Dependency.fields.fields))

        names = set(
            filter(None, map(lambda x: x.get(Recipe.fields.name), dump)))
        self.assertNotIn('Pico de Gallo', names)
        self.assertNotIn('Guacamole', names)

        ids = set(filter(None, map(lambda x: x.get(Recipe.fields.id), dump)))
        self.assertSetEqual({fajitas_id}, ids)

    def test_read_join_model_columns(self):
        dump = self.driver.read(
            (
                Dependency,
                Recipe,
                Dependency.fields.requisite,
                Recipe.fields.id,
            ),
            columns={
                Recipe.fields.name,
                Dependency.fields.required_by,
            },
        )

        self.assertEqual(len(dump), 3)
        self.assertSetEqual(set(dump[0].keys()), {
            Recipe.fields.name,
            Dependency.fields.required_by,
        })


class TestDriverJSONWrite(TestCase):

    def setUp(self):
        json = """{
    "recipes": {
        "1": {
            "id": "7fa1f29e27a48cc8dc73cbdcdec7231ff4923bd1520fc8e6e3413547172d490d",
            "name": "Fajitas",
            "simple_name": "fajitas",
            "author": "",
            "directions": "",
            "information": ""
        }
    }
}
"""
        with NamedTemporaryFile(mode='w',
                                encoding='utf-8',
                                delete=False,
                                suffix='.json') as temp:
            self.datafile = temp
            self.datafile.write(json)

        self.driver = JSONDriver(self.datafile.name)

    def tearDown(self):
        self.datafile.close()
        self.driver.db.close()
        Path(self.datafile.name).unlink()

    def test_write_model(self):
        self.driver.write(
            Recipe,
            Recipe(**dict(
                name="Guacamole",
                author="jb",
                directions="Split the avocados, ...",
            )).params)

        with open(self.datafile.name, 'r') as datafile:
            dump = datafile.read()
            datafile.close()

        self.assertIn('"name": "Guacamole"', dump)
        self.assertIn('"directions": "Split the avocados, ..."', dump)

    def test_write_model_field(self):
        fajitas_id = '7fa1f29e27a48cc8dc73cbdcdec7231ff4923bd1520fc8e6e3413547172d490d'
        self.driver.write(
            Recipe,
            {
                Recipe.fields.name: "Fajititas",
                Recipe.fields.simple_name: "fajititas",
            },
            filters=[{
                Recipe.fields.id: fajitas_id
            }],
        )

        with open(self.datafile.name, 'r') as datafile:
            dump = datafile.read()

        self.assertNotIn("Fajitas", dump)
        self.assertNotIn("fajitas", dump)
        self.assertIn("Fajititas", dump)
        self.assertIn("fajititas", dump)


class TestDriverJSONErase(TestCase):

    def setUp(self):
        json = """{
    "recipes": {
        "1": {
            "id": "7fa1f29e27a48cc8dc73cbdcdec7231ff4923bd1520fc8e6e3413547172d490d",
            "name": "Fajitas",
            "simple_name": "fajitas",
            "author": "",
            "directions": "",
            "information": ""
        },
        "2": {
            "id": "06faab5fe9048cf9a5d009952e3e491fb4b785cf38a6230f450167004f3733ed",
            "name": "Guacamole",
            "simple_name": "guacamole",
            "author": "",
            "directions": "",
            "information": ""
        }
    }
}
"""
        with NamedTemporaryFile(mode='w',
                                encoding='utf-8',
                                delete=False,
                                suffix='.json') as temp:
            self.datafile = temp
            self.datafile.write(json)

        self.driver = JSONDriver(self.datafile.name)

    def tearDown(self):
        self.datafile.close()
        self.driver.db.close()
        Path(self.datafile.name).unlink()

    def test_erase_model(self):
        with self.assertRaises(ValueError):
            self.driver.erase(Recipe)

    def test_erase_model_filtered(self):
        self.driver.erase(Recipe, filters=[{Recipe.fields.name: "Guacamole"}])

        with open(self.datafile.name, 'r') as datafile:
            dump = datafile.read()

        self.assertNotIn("Guacamole", dump)
        self.assertNotIn("Split the avocados, ...", dump)
        self.assertIn("Fajitas", dump)
        self.assertIn("id", dump)

    def test_erase_model_filtered_multiple(self):
        self.driver.erase(Recipe, filters=[{Recipe.fields.author: ""}])

        with open(self.datafile.name, 'r') as datafile:
            dump = datafile.read()

        self.assertNotIn("Guacamole", dump)
        self.assertNotIn("Split the avocados, ...", dump)
        self.assertNotIn("Fajitas", dump)
        self.assertNotIn("id", dump)
