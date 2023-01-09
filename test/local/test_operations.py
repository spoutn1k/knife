from pathlib import Path
from knife.models import Recipe, Dependency
from knife.drivers.json import JSONDriver
from knife.operations import (dependency_nodes, dependency_list,
                              requirement_list, tag_list)
from test import TestCase
from tempfile import NamedTemporaryFile


class TestOperations(TestCase):

    def setUp(self):
        self.fajitas_id = "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c"
        self.guacamole_id = "8a97dd5724a9e3060191f7b616f5aaa3f529cdb5c555995f6a6dee2f5f79dfd2"
        self.pico_de_gallo_id = "a86eb5eae40d8d58f38b3416f48b414e6d82e4ba6a7c7bce89ed05f0c4e8d536"
        self.chipotle_chicken_id = "5158f09fa8e396a478095953a3177b1e3ec353078050b94f13a7a2cf54371cf2"
        self.horchata_id = "809b86f439c3cafa53d843817a0eb2e9339e8c52dd94052df8f202178578523f"

        self.bell_pepper_id = "16ec950875db0fc61feb72f31c82d94af9e6ca572b1b350e287d32dd2314fbe1"
        self.onion_id = "99c6b45b97f6e6aef1a3cdc6acfbf2fa3122f0b73c70c6256e94b86b258547fb"
        self.jalapeno_id = "3cf03e09ac3b0f0d5aaa53c018a038614dc321fb7bc7295a4fbc7a4c3ce28665"

        self.mexican_id = "a38985fe971482b9c489e196ce9b4046b5755c12d7ff1729ff101558f3ee71b9"
        self.drink_id = "473e7cd6c7ee532d7ee62322c6c3c019445bb965d7b3bc69554e6f31c6cd34de"

        json = """{
    "recipes": {
        "6": {
            "id": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "name": "Fajitas",
            "simple_name": "fajitas",
            "author": "",
            "directions": ""
        },
        "7": {
            "id": "8a97dd5724a9e3060191f7b616f5aaa3f529cdb5c555995f6a6dee2f5f79dfd2",
            "name": "Guacamole",
            "simple_name": "guacamole",
            "author": "",
            "directions": ""
        },
        "8": {
            "id": "5158f09fa8e396a478095953a3177b1e3ec353078050b94f13a7a2cf54371cf2",
            "name": "Chipotle Chicken",
            "simple_name": "chipotle_chicken",
            "author": "",
            "directions": ""
        },
        "9": {
            "id": "a86eb5eae40d8d58f38b3416f48b414e6d82e4ba6a7c7bce89ed05f0c4e8d536",
            "name": "Pico de Gallo",
            "simple_name": "pico_de_gallo",
            "author": "",
            "directions": ""
        },
        "10": {
            "id": "809b86f439c3cafa53d843817a0eb2e9339e8c52dd94052df8f202178578523f",
            "name": "Horchata",
            "simple_name": "horchata",
            "author": "",
            "directions": ""
        }
    },
    "dependencies": {
        "4": {
            "required_by": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "requisite": "8a97dd5724a9e3060191f7b616f5aaa3f529cdb5c555995f6a6dee2f5f79dfd2",
            "quantity": ""
        },
        "5": {
            "required_by": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "requisite": "5158f09fa8e396a478095953a3177b1e3ec353078050b94f13a7a2cf54371cf2",
            "quantity": ""
        },
        "6": {
            "required_by": "8a97dd5724a9e3060191f7b616f5aaa3f529cdb5c555995f6a6dee2f5f79dfd2",
            "requisite": "a86eb5eae40d8d58f38b3416f48b414e6d82e4ba6a7c7bce89ed05f0c4e8d536",
            "quantity": ""
        }
    },
    "labels": {
        "2": {
            "id": "a38985fe971482b9c489e196ce9b4046b5755c12d7ff1729ff101558f3ee71b9",
            "name": "mexican",
            "simple_name": "mexican"
        },
        "3": {
            "id": "473e7cd6c7ee532d7ee62322c6c3c019445bb965d7b3bc69554e6f31c6cd34de",
            "name": "drink",
            "simple_name": "drink"
        },
        "4": {
            "id": "464223c5d6a1b972bd9481123175ffbeaaeabc9aa259cd00f0e4040f37956f18",
            "name": "spicy",
            "simple_name": "spicy"
        }
    },
    "tags": {
        "6": {
            "recipe_id": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "label_id": "a38985fe971482b9c489e196ce9b4046b5755c12d7ff1729ff101558f3ee71b9"
        },
        "7": {
            "recipe_id": "8a97dd5724a9e3060191f7b616f5aaa3f529cdb5c555995f6a6dee2f5f79dfd2",
            "label_id": "a38985fe971482b9c489e196ce9b4046b5755c12d7ff1729ff101558f3ee71b9"
        },
        "8": {
            "recipe_id": "5158f09fa8e396a478095953a3177b1e3ec353078050b94f13a7a2cf54371cf2",
            "label_id": "a38985fe971482b9c489e196ce9b4046b5755c12d7ff1729ff101558f3ee71b9"
        },
        "9": {
            "recipe_id": "a86eb5eae40d8d58f38b3416f48b414e6d82e4ba6a7c7bce89ed05f0c4e8d536",
            "label_id": "a38985fe971482b9c489e196ce9b4046b5755c12d7ff1729ff101558f3ee71b9"
        },
        "10": {
            "recipe_id": "809b86f439c3cafa53d843817a0eb2e9339e8c52dd94052df8f202178578523f",
            "label_id": "a38985fe971482b9c489e196ce9b4046b5755c12d7ff1729ff101558f3ee71b9"
        },
        "11": {
            "recipe_id": "809b86f439c3cafa53d843817a0eb2e9339e8c52dd94052df8f202178578523f",
            "label_id": "473e7cd6c7ee532d7ee62322c6c3c019445bb965d7b3bc69554e6f31c6cd34de"
        },
        "12": {
            "recipe_id": "5158f09fa8e396a478095953a3177b1e3ec353078050b94f13a7a2cf54371cf2",
            "label_id": "464223c5d6a1b972bd9481123175ffbeaaeabc9aa259cd00f0e4040f37956f18"
        }
    },
    "ingredients": {
        "4": {
            "id": "16ec950875db0fc61feb72f31c82d94af9e6ca572b1b350e287d32dd2314fbe1",
            "name": "Bell Pepper",
            "simple_name": "bell_pepper"
        },
        "5": {
            "id": "99c6b45b97f6e6aef1a3cdc6acfbf2fa3122f0b73c70c6256e94b86b258547fb",
            "name": "Onion",
            "simple_name": "onion"
        },
        "6": {
            "id": "3cf03e09ac3b0f0d5aaa53c018a038614dc321fb7bc7295a4fbc7a4c3ce28665",
            "name": "Jalapeno",
            "simple_name": "jalapeno"
        }
    },
    "requirements": {
        "5": {
            "recipe_id": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "ingredient_id": "16ec950875db0fc61feb72f31c82d94af9e6ca572b1b350e287d32dd2314fbe1",
            "quantity": "4"
        },
        "6": {
            "recipe_id": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "ingredient_id": "99c6b45b97f6e6aef1a3cdc6acfbf2fa3122f0b73c70c6256e94b86b258547fb",
            "quantity": "1"
        },
        "7": {
            "recipe_id": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "ingredient_id": "3cf03e09ac3b0f0d5aaa53c018a038614dc321fb7bc7295a4fbc7a4c3ce28665",
            "quantity": "2"
        },
        "8": {
            "recipe_id": "a86eb5eae40d8d58f38b3416f48b414e6d82e4ba6a7c7bce89ed05f0c4e8d536",
            "ingredient_id": "3cf03e09ac3b0f0d5aaa53c018a038614dc321fb7bc7295a4fbc7a4c3ce28665",
            "quantity": "2"
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

    def test_dependency_nodes(self):
        nodes = dependency_nodes(self.driver, self.fajitas_id)

        self.assertSetEqual(
            nodes, {
                self.fajitas_id,
                self.guacamole_id,
                self.pico_de_gallo_id,
                self.chipotle_chicken_id,
            })

        nodes = dependency_nodes(self.driver, self.guacamole_id)

        self.assertSetEqual(nodes, {
            self.guacamole_id,
            self.pico_de_gallo_id,
        })

        nodes = dependency_nodes(self.driver, self.horchata_id)

        self.assertSetEqual(nodes, {
            self.horchata_id,
        })

    def test_dependency_list(self):
        dependencies = dependency_list(self.driver, self.fajitas_id)
        self.assertEqual(len(dependencies), 2)

        listed = set()
        for dependency in dependencies:
            self.assertIn('recipe', dependency)
            self.assertIn('id', dependency['recipe'])
            listed.add(dependency['recipe']['id'])

        self.assertSetEqual(listed, {
            self.guacamole_id,
            self.chipotle_chicken_id,
        })

        dependencies = dependency_list(self.driver, self.horchata_id)
        self.assertEqual(len(dependencies), 0)

    def test_requirement_list(self):
        requirements = requirement_list(self.driver, self.fajitas_id)
        self.assertEqual(len(requirements), 3)

        listed = set()
        for requirement in requirements:
            self.assertIn('ingredient', requirement)
            self.assertIn('id', requirement['ingredient'])
            listed.add(requirement['ingredient']['id'])

        self.assertSetEqual(listed, {
            self.bell_pepper_id,
            self.onion_id,
            self.jalapeno_id,
        })

        requirements = requirement_list(self.driver, self.guacamole_id)
        self.assertEqual(len(requirements), 0)

    def test_tag_list(self):
        tags = tag_list(self.driver, self.horchata_id)
        self.assertEqual(len(tags), 2)

        listed = set()
        for tag in tags:
            self.assertIn('id', tag)
            listed.add(tag['id'])

        self.assertSetEqual(listed, {
            self.mexican_id,
            self.drink_id,
        })

        tags = tag_list(self.driver, self.guacamole_id)
        self.assertEqual(len(tags), 1)
