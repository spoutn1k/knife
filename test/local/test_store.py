from pathlib import Path
from knife.store import Store
from knife.exceptions import (
    DependencyNotFound,
    EmptyQuery,
    IngredientAlreadyExists,
    IngredientInUse,
    IngredientNotFound,
    InvalidQuery,
    LabelAlreadyExists,
    #LabelInUse,
    LabelNotFound,
    RecipeAlreadyExists,
    #RecipeInUse,
    RecipeNotFound,
    RequirementNotFound,
    TagNotFound,
)
from knife.models import (
    Dependency,
    Ingredient,
    Label,
    Recipe,
    Requirement,
    Tag,
)
from knife.drivers.json import JSONDriver
from knife.operations import (
    dependency_nodes,
    dependency_list,
    requirement_list,
    tag_list,
)
from test import TestCase
from tempfile import NamedTemporaryFile


class TestStore(TestCase):

    def setUp(self):
        self.maxDiff = 8192
        self.fajitas_id = "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c"
        self.guacamole_id = "8a97dd5724a9e3060191f7b616f5aaa3f529cdb5c555995f6a6dee2f5f79dfd2"
        self.pico_de_gallo_id = "a86eb5eae40d8d58f38b3416f48b414e6d82e4ba6a7c7bce89ed05f0c4e8d536"
        self.chipotle_chicken_id = "5158f09fa8e396a478095953a3177b1e3ec353078050b94f13a7a2cf54371cf2"
        self.horchata_id = "809b86f439c3cafa53d843817a0eb2e9339e8c52dd94052df8f202178578523f"

        self.bell_pepper_id = "16ec950875db0fc61feb72f31c82d94af9e6ca572b1b350e287d32dd2314fbe1"
        self.onion_id = "99c6b45b97f6e6aef1a3cdc6acfbf2fa3122f0b73c70c6256e94b86b258547fb"
        self.jalapeno_id = "3cf03e09ac3b0f0d5aaa53c018a038614dc321fb7bc7295a4fbc7a4c3ce28665"
        self.serrano_id = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        self.mexican_id = "a38985fe971482b9c489e196ce9b4046b5755c12d7ff1729ff101558f3ee71b9"
        self.drink_id = "473e7cd6c7ee532d7ee62322c6c3c019445bb965d7b3bc69554e6f31c6cd34de"
        self.vegan_id = "33d30cbbb689b326006570b74f1dc42ae4c098e3b7e24e0441070b721b56a0e7"

        json = """{
    "recipes": {
        "6": {
            "id": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "name": "Fajitas",
            "simple_name": "fajitas",
            "author": "",
            "information": "",
            "directions": ""
        },
        "7": {
            "id": "8a97dd5724a9e3060191f7b616f5aaa3f529cdb5c555995f6a6dee2f5f79dfd2",
            "name": "Guacamole",
            "simple_name": "guacamole",
            "author": "",
            "information": "",
            "directions": ""
        },
        "8": {
            "id": "5158f09fa8e396a478095953a3177b1e3ec353078050b94f13a7a2cf54371cf2",
            "name": "Chipotle Chicken",
            "simple_name": "chipotle_chicken",
            "author": "",
            "information": "",
            "directions": ""
        },
        "9": {
            "id": "a86eb5eae40d8d58f38b3416f48b414e6d82e4ba6a7c7bce89ed05f0c4e8d536",
            "name": "Pico de Gallo",
            "simple_name": "pico_de_gallo",
            "author": "",
            "information": "",
            "directions": ""
        },
        "10": {
            "id": "809b86f439c3cafa53d843817a0eb2e9339e8c52dd94052df8f202178578523f",
            "name": "Horchata",
            "simple_name": "horchata",
            "author": "",
            "information": "",
            "directions": ""
        }
    },
    "dependencies": {
        "4": {
            "required_by": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "requisite": "8a97dd5724a9e3060191f7b616f5aaa3f529cdb5c555995f6a6dee2f5f79dfd2",
            "quantity": "1 cup",
            "optional": false
        },
        "5": {
            "required_by": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "requisite": "5158f09fa8e396a478095953a3177b1e3ec353078050b94f13a7a2cf54371cf2",
            "quantity": "A little bit",
            "optional": false
        },
        "6": {
            "required_by": "8a97dd5724a9e3060191f7b616f5aaa3f529cdb5c555995f6a6dee2f5f79dfd2",
            "requisite": "a86eb5eae40d8d58f38b3416f48b414e6d82e4ba6a7c7bce89ed05f0c4e8d536",
            "quantity": "",
            "optional": false
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
        },
        "5": {
            "id": "33d30cbbb689b326006570b74f1dc42ae4c098e3b7e24e0441070b721b56a0e7",
            "name": "vegan",
            "simple_name": "vegan"
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
            "simple_name": "bell_pepper",
            "dairy": false,
            "gluten": false,
            "meat": false,
            "animal_product": false

        },
        "5": {
            "id": "99c6b45b97f6e6aef1a3cdc6acfbf2fa3122f0b73c70c6256e94b86b258547fb",
            "name": "Onion",
            "simple_name": "onion",
            "dairy": false,
            "gluten": false,
            "meat": false,
            "animal_product": false

        },
        "6": {
            "id": "3cf03e09ac3b0f0d5aaa53c018a038614dc321fb7bc7295a4fbc7a4c3ce28665",
            "name": "Jalapeño",
            "simple_name": "jalapeno",
            "dairy": false,
            "gluten": false,
            "meat": false,
            "animal_product": false

        },
        "7": {
            "id": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "name": "Serrano",
            "simple_name": "serrano",
            "dairy": false,
            "gluten": false,
            "meat": false,
            "animal_product": false

        }
    },
    "requirements": {
        "5": {
            "recipe_id": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "ingredient_id": "16ec950875db0fc61feb72f31c82d94af9e6ca572b1b350e287d32dd2314fbe1",
            "quantity": "4",
            "optional": false,
            "group": ""
        },
        "6": {
            "recipe_id": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "ingredient_id": "99c6b45b97f6e6aef1a3cdc6acfbf2fa3122f0b73c70c6256e94b86b258547fb",
            "quantity": "1",
            "optional": false,
            "group": ""
        },
        "7": {
            "recipe_id": "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
            "ingredient_id": "3cf03e09ac3b0f0d5aaa53c018a038614dc321fb7bc7295a4fbc7a4c3ce28665",
            "quantity": "2",
            "optional": false,
            "group": ""
        },
        "8": {
            "recipe_id": "a86eb5eae40d8d58f38b3416f48b414e6d82e4ba6a7c7bce89ed05f0c4e8d536",
            "ingredient_id": "3cf03e09ac3b0f0d5aaa53c018a038614dc321fb7bc7295a4fbc7a4c3ce28665",
            "quantity": "2",
            "optional": false,
            "group": ""
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
        self.store = Store(self.driver)

    def tearDown(self):
        self.datafile.close()
        self.driver.db.close()
        Path(self.datafile.name).unlink()

    def test_recipe_create(self):
        self.store._recipe_create({},
                                  dict(
                                      name='Tartare',
                                      author='me',
                                      directions='Cut the steak.',
                                  ))

        saved = self.driver.read(Recipe, [{Recipe.fields.name: 'Tartare'}])
        self.assertEqual(len(saved), 1)
        self.assertEqual(
            saved[0],
            saved[0] | {
                Recipe.fields.name: 'Tartare',
                Recipe.fields.author: 'me',
                Recipe.fields.directions: 'Cut the steak.',
            },
        )

    def test_recipe_create_existing(self):
        with self.assertRaises(RecipeAlreadyExists):
            self.store._recipe_create({}, dict(name='Fajitas'))

        saved = self.driver.read(
            Recipe,
            [{
                Recipe.fields.name: 'Fajitas'
            }],
            exact=True,
        )
        self.assertEqual(len(saved), 1)

    def test_recipe_create_empty(self):
        with self.assertRaises(EmptyQuery):
            self.store._recipe_create({}, dict())

        saved = self.driver.read(Recipe)
        self.assertEqual(len(saved), 5)

    def test_recipe_create_unnamed(self):
        with self.assertRaises(InvalidQuery):
            self.store._recipe_create({}, dict(author="me"))

        saved = self.driver.read(Recipe)
        self.assertEqual(len(saved), 5)

    def test_recipe_create_junk_args(self):
        with self.assertRaises(InvalidQuery):
            self.store._recipe_create({}, dict(name='Tartare', btw='junk'))

        saved = self.driver.read(
            Recipe,
            [{
                Recipe.fields.name: 'Tartare'
            }],
            exact=True,
        )
        self.assertEqual(len(saved), 0)

    def test_recipe_lookup(self):
        lookup = self.store._recipe_lookup({}, {})
        for index in [{
                "id":
                "f220c36c654f994128a0b8c9099ee1aba3349fb446bc8606aae07855194a7a7c",
                "name": "Fajitas",
        }, {
                "id":
                "8a97dd5724a9e3060191f7b616f5aaa3f529cdb5c555995f6a6dee2f5f79dfd2",
                "name": "Guacamole",
        }, {
                "id":
                "5158f09fa8e396a478095953a3177b1e3ec353078050b94f13a7a2cf54371cf2",
                "name": "Chipotle Chicken",
        }, {
                "id":
                "a86eb5eae40d8d58f38b3416f48b414e6d82e4ba6a7c7bce89ed05f0c4e8d536",
                "name": "Pico de Gallo",
        }, {
                "id":
                "809b86f439c3cafa53d843817a0eb2e9339e8c52dd94052df8f202178578523f",
                "name": "Horchata",
        }]:
            self.assertIn(index, lookup)

    def test_recipe_lookup_filter_name(self):
        lookup = self.store._recipe_lookup(dict(name='ji'), {})
        self.assertListEqual(lookup, [{
            "id": self.fajitas_id,
            "name": "Fajitas",
        }])

        lookup = self.store._recipe_lookup(dict(name='Hor'), {})
        self.assertListEqual(lookup, [{
            "id": self.horchata_id,
            "name": "Horchata",
        }])

    def test_recipe_lookup_junk_args(self):
        with self.assertRaises(InvalidQuery):
            self.store._recipe_lookup(dict(name='Tartare', btw='junk'), {})

    def test_recipe_delete(self):
        self.store._recipe_delete(self.horchata_id, {}, {})

        saved = self.driver.read(
            Recipe,
            [{
                Recipe.fields.name: 'Horchata'
            }],
            exact=True,
        )
        self.assertEqual(len(saved), 0)

    #TODO
    """
    def test_recipe_delete_in_use(self):
        with self.assertRaises(RecipeInUse):
            self.store._recipe_delete(self.guacamole_id, {}, {})

        saved = self.driver.read(
            Recipe,
            [{
                Recipe.fields.name: 'Guacamole'
            }],
            exact=True,
        )
        self.assertEqual(len(saved), 1)
    """

    def test_recipe_delete_bad_id(self):
        with self.assertRaises(RecipeNotFound):
            self.store._recipe_delete('badid', {}, {})

        saved = self.driver.read(Recipe, )
        self.assertEqual(len(saved), 5)

    def test_recipe_requirements(self):
        saved = self.store._recipe_requirements(self.fajitas_id, {}, {})
        self.assertEqual(len(saved), 3)

        for element in saved:
            self.assertTrue({
                Requirement.fields.quantity.name,
                'ingredient',
            }.issubset(set(element)))

            self.assertTrue({
                'id',
                'name',
            }.issubset(set(element['ingredient'])))

        quantities = set(
            map(lambda x: x[Requirement.fields.quantity.name], saved))
        ingredient_names = set(map(lambda x: x['ingredient']['name'], saved))

        self.assertSetEqual(quantities, {"1", "2", "4"})
        self.assertSetEqual(ingredient_names,
                            {"Bell Pepper", "Onion", "Jalapeño"})

    def test_recipe_requirements_bad_id(self):
        with self.assertRaises(RecipeNotFound):
            self.store._recipe_requirements('badid', {}, {})

    def test_recipe_dependencies(self):
        saved = self.store._recipe_dependencies(self.fajitas_id, {}, {})
        self.assertEqual(len(saved), 2)

        for element in saved:
            # Assert the expected keys are in the set
            self.assertTrue({
                Dependency.fields.quantity.name,
                'recipe',
            }.issubset(set(element)))

            self.assertTrue({
                'id',
                'name',
            }.issubset(set(element['recipe'])))

        quantities = set(
            map(lambda x: x[Dependency.fields.quantity.name], saved))
        dependency_names = set(map(lambda x: x['recipe']['name'], saved))

        self.assertSetEqual(quantities, {"1 cup", "A little bit"})
        self.assertSetEqual(dependency_names,
                            {"Guacamole", "Chipotle Chicken"})

    def test_recipe_dependencies_bad_id(self):
        with self.assertRaises(RecipeNotFound):
            self.store._recipe_dependencies('badid', {}, {})

    def test_recipe_tags(self):
        saved = self.store._recipe_tags(self.fajitas_id, {}, {})
        self.assertEqual(len(saved), 1)

        for element in saved:
            # Assert the expected keys are in the set
            self.assertTrue({
                'id',
                'name',
            }.issubset(set(element)))

        label_names = set(map(lambda x: x['name'], saved))

        self.assertSetEqual(label_names, {"mexican"})

    def test_recipe_tags_bad_id(self):
        with self.assertRaises(RecipeNotFound):
            self.store._recipe_tags('badid', {}, {})

    def test_recipe_get(self):
        saved = self.store._recipe_get(self.fajitas_id, {}, {})

        keys = {
            'id',
            'name',
            'author',
            'directions',
            'requirements',
            'dependencies',
            'tags',
        }
        self.assertTrue(keys.issubset(set(saved)),
                        msg=f"{keys} not in {set(saved)}")

        self.assertEqual(
            saved,
            saved | {
                "id": self.fajitas_id,
                "name": "Fajitas",
                "author": "",
                "directions": "",
            },
        )

        self.assertEqual(len(saved['requirements']), 3)
        self.assertEqual(len(saved['dependencies']), 2)
        self.assertEqual(len(saved['tags']), 1)

    def test_recipe_get_bad_id(self):
        with self.assertRaises(RecipeNotFound):
            self.store._recipe_get('badid', {}, {})

    def test_recipe_edit_name(self):
        self.store._recipe_edit(
            self.fajitas_id,
            {},
            dict(name='Fajititas'),
        )

        saved = self.driver.read(Recipe, [{
            Recipe.fields.id: self.fajitas_id,
        }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Recipe.fields.id: self.fajitas_id,
                Recipe.fields.name: "Fajititas",
                Recipe.fields.simple_name: "fajititas",
                Recipe.fields.author: "",
                Recipe.fields.directions: "",
                Recipe.fields.information: "",
            },
        )

    def test_recipe_edit_author(self):
        self.store._recipe_edit(
            self.fajitas_id,
            {},
            dict(author='me'),
        )

        saved = self.driver.read(Recipe, [{
            Recipe.fields.id: self.fajitas_id,
        }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Recipe.fields.id: self.fajitas_id,
                Recipe.fields.name: "Fajitas",
                Recipe.fields.simple_name: "fajitas",
                Recipe.fields.author: "me",
                Recipe.fields.directions: "",
                Recipe.fields.information: "",
            },
        )

    def test_recipe_edit_directions(self):
        text = "Do this and that !"

        self.store._recipe_edit(
            self.fajitas_id,
            {},
            dict(directions=text),
        )

        saved = self.driver.read(Recipe, [{
            Recipe.fields.id: self.fajitas_id,
        }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Recipe.fields.id: self.fajitas_id,
                Recipe.fields.name: "Fajitas",
                Recipe.fields.simple_name: "fajitas",
                Recipe.fields.author: "",
                Recipe.fields.directions: text,
                Recipe.fields.information: "",
            },
        )

    def test_recipe_edit_information(self):
        text = "Do this and that !"

        self.store._recipe_edit(
            self.fajitas_id,
            {},
            dict(information=text),
        )

        saved = self.driver.read(Recipe, [{
            Recipe.fields.id: self.fajitas_id,
        }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Recipe.fields.id: self.fajitas_id,
                Recipe.fields.name: "Fajitas",
                Recipe.fields.simple_name: "fajitas",
                Recipe.fields.author: "",
                Recipe.fields.directions: "",
                Recipe.fields.information: text,
            },
        )

    def test_recipe_edit_bad_id(self):
        with self.assertRaises(RecipeNotFound):
            self.store._recipe_edit('badid', {}, dict(name='junk'))

    def test_recipe_edit_junk_form(self):
        with self.assertRaises(InvalidQuery):
            self.store._recipe_edit(self.fajitas_id, {},
                                    dict(
                                        name='junk',
                                        btw='something',
                                    ))

        saved = self.driver.read(Recipe, [{Recipe.fields.id: self.fajitas_id}])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Recipe.fields.id: self.fajitas_id,
                Recipe.fields.name: "Fajitas",
                Recipe.fields.simple_name: "fajitas",
                Recipe.fields.author: "",
                Recipe.fields.directions: "",
            },
        )

    def test_recipe_edit_existing_name(self):
        with self.assertRaises(RecipeAlreadyExists):
            self.store._recipe_edit(self.fajitas_id, {}, dict(name='Horchata'))

        saved = self.driver.read(Recipe, [{Recipe.fields.id: self.fajitas_id}])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Recipe.fields.id: self.fajitas_id,
                Recipe.fields.name: "Fajitas",
                Recipe.fields.simple_name: "fajitas",
                Recipe.fields.author: "",
                Recipe.fields.directions: "",
            },
        )

    def test_ingredient_create(self):
        self.store._ingredient_create({}, dict(name='Habanero', ))

        saved = self.driver.read(Ingredient,
                                 [{
                                     Ingredient.fields.name: 'Habanero'
                                 }])
        self.assertEqual(len(saved), 1)
        self.assertEqual(
            saved[0],
            saved[0] | {
                Ingredient.fields.name: 'Habanero',
                Ingredient.fields.dairy: False,
                Ingredient.fields.meat: False,
                Ingredient.fields.gluten: False,
                Ingredient.fields.animal_product: False,
            },
        )

    def test_ingredient_create_with_restriction(self):
        self.store._ingredient_create({}, dict(
            name='Queso',
            dairy=True,
        ))

        saved = self.driver.read(Ingredient, [{
            Ingredient.fields.name: 'Queso'
        }])
        self.assertEqual(len(saved), 1)
        self.assertEqual(
            saved[0],
            saved[0] | {
                Ingredient.fields.name: 'Queso',
                Ingredient.fields.dairy: True,
                Ingredient.fields.meat: False,
                Ingredient.fields.gluten: False,
                Ingredient.fields.animal_product: False,
            },
        )

        self.store._ingredient_create({},
                                      dict(
                                          name='Chorizo',
                                          meat=True,
                                          animal_product=True,
                                      ))

        saved = self.driver.read(Ingredient, [{
            Ingredient.fields.name: 'Chorizo'
        }])
        self.assertEqual(len(saved), 1)
        self.assertEqual(
            saved[0],
            saved[0] | {
                Ingredient.fields.name: 'Chorizo',
                Ingredient.fields.dairy: False,
                Ingredient.fields.meat: True,
                Ingredient.fields.gluten: False,
                Ingredient.fields.animal_product: True,
            },
        )

        self.store._ingredient_create({},
                                      dict(
                                          name='Flour tortilla',
                                          gluten=True,
                                      ))

        saved = self.driver.read(Ingredient,
                                 [{
                                     Ingredient.fields.name: 'Flour tortilla'
                                 }])
        self.assertEqual(len(saved), 1)
        self.assertEqual(
            saved[0],
            saved[0] | {
                Ingredient.fields.name: 'Flour tortilla',
                Ingredient.fields.dairy: False,
                Ingredient.fields.meat: False,
                Ingredient.fields.gluten: True,
                Ingredient.fields.animal_product: False,
            },
        )

    def test_ingredient_create_empty(self):
        with self.assertRaises(InvalidQuery):
            self.store._ingredient_create({}, dict())

        saved = self.driver.read(Ingredient)
        self.assertEqual(len(saved), 4)

    def test_ingredient_create_unnamed(self):
        with self.assertRaises(InvalidQuery):
            self.store._ingredient_create({}, dict(dairy=True))

        saved = self.driver.read(Ingredient)
        self.assertEqual(len(saved), 4)

    def test_ingredient_create_existing(self):
        with self.assertRaises(IngredientAlreadyExists):
            self.store._ingredient_create({}, dict(name='Onion'))

        saved = self.driver.read(
            Ingredient,
            [{
                Ingredient.fields.name: 'Onion'
            }],
            exact=True,
        )
        self.assertEqual(len(saved), 1)

    def test_ingredient_create_junk_args(self):
        with self.assertRaises(InvalidQuery):
            self.store._ingredient_create({}, dict(name='Habanero',
                                                   btw='junk'))

        saved = self.driver.read(
            Ingredient,
            [{
                Ingredient.fields.name: 'Habanero'
            }],
            exact=True,
        )
        self.assertEqual(len(saved), 0)

    def test_ingredient_lookup(self):
        lookup = self.store._ingredient_lookup({}, {})
        for index in [{
                "id":
                "16ec950875db0fc61feb72f31c82d94af9e6ca572b1b350e287d32dd2314fbe1",
                "name": "Bell Pepper",
        }, {
                "id":
                "99c6b45b97f6e6aef1a3cdc6acfbf2fa3122f0b73c70c6256e94b86b258547fb",
                "name": "Onion",
        }, {
                "id":
                "3cf03e09ac3b0f0d5aaa53c018a038614dc321fb7bc7295a4fbc7a4c3ce28665",
                "name": "Jalapeño",
        }, {
                "id":
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "name": "Serrano",
        }]:
            self.assertIn(index, lookup)

    def test_ingredient_lookup_filter_name(self):
        lookup = self.store._ingredient_lookup(dict(name='nio'), {})
        self.assertListEqual(lookup, [{
            "id": self.onion_id,
            "name": "Onion",
        }])

        lookup = self.store._ingredient_lookup(dict(name='Jala'), {})
        self.assertListEqual(lookup, [{
            "id": self.jalapeno_id,
            "name": "Jalapeño",
        }])

    def test_ingredient_lookup_junk_args(self):
        with self.assertRaises(InvalidQuery):
            self.store._ingredient_lookup(dict(name='Habanero', btw='junk'),
                                          {})

    def test_ingredient_delete(self):
        self.store._ingredient_delete(self.serrano_id, {}, {})

        saved = self.driver.read(
            Ingredient,
            [{
                Ingredient.fields.name: 'Serrano'
            }],
            exact=True,
        )
        self.assertEqual(len(saved), 0)

    def test_ingredient_delete_in_use(self):
        with self.assertRaises(IngredientInUse):
            self.store._ingredient_delete(self.jalapeno_id, {}, {})

        saved = self.driver.read(
            Ingredient,
            [{
                Ingredient.fields.name: 'Jalapeño'
            }],
            exact=True,
        )
        self.assertEqual(len(saved), 1)

    def test_ingredient_delete_bad_id(self):
        with self.assertRaises(IngredientNotFound):
            self.store._ingredient_delete('badid', {}, {})

        saved = self.driver.read(Ingredient, )
        self.assertEqual(len(saved), 4)

    def test_ingredient_show(self):
        saved = self.store._ingredient_show(self.onion_id, {}, {})

        self.assertTrue({
            'id',
            'name',
            'used_in',
        }.issubset(set(saved)))

        self.assertEqual(
            saved,
            saved | {
                "id": self.onion_id,
                "name": "Onion",
            },
        )

        self.assertEqual(len(saved['used_in']), 1)

    def test_ingredient_show_bad_id(self):
        with self.assertRaises(IngredientNotFound):
            self.store._ingredient_show('badid', {}, {})

    def test_ingredient_edit_name(self):
        saved = self.store._ingredient_edit(
            self.onion_id,
            {},
            dict(name='Red Onion'),
        )

        saved = self.driver.read(Ingredient,
                                 [{
                                     Ingredient.fields.id: self.onion_id,
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            {
                Ingredient.fields.id: self.onion_id,
                Ingredient.fields.name: "Red Onion",
                Ingredient.fields.simple_name: "red_onion",
                Ingredient.fields.dairy: False,
                Ingredient.fields.meat: False,
                Ingredient.fields.gluten: False,
                Ingredient.fields.animal_product: False,
            },
        )

    def test_ingredient_edit_dairy(self):
        saved = self.store._ingredient_edit(
            self.onion_id,
            {},
            dict(dairy=True),
        )

        saved = self.driver.read(Ingredient,
                                 [{
                                     Ingredient.fields.id: self.onion_id,
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            {
                Ingredient.fields.id: self.onion_id,
                Ingredient.fields.name: "Onion",
                Ingredient.fields.simple_name: "onion",
                Ingredient.fields.dairy: True,
                Ingredient.fields.meat: False,
                Ingredient.fields.gluten: False,
                Ingredient.fields.animal_product: False,
            },
        )

    def test_ingredient_edit_bad_id(self):
        with self.assertRaises(IngredientNotFound):
            self.store._ingredient_edit('badid', {}, dict(name='junk'))

    def test_ingredient_edit_junk_form(self):
        with self.assertRaises(InvalidQuery):
            self.store._ingredient_edit(self.onion_id, {},
                                        dict(
                                            name='junk',
                                            btw='something',
                                        ))

        saved = self.driver.read(Ingredient,
                                 [{
                                     Ingredient.fields.id: self.onion_id
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Ingredient.fields.id: self.onion_id,
                Ingredient.fields.name: "Onion",
                Ingredient.fields.simple_name: "onion",
            },
        )

    def test_ingredient_edit_existing_name(self):
        with self.assertRaises(IngredientAlreadyExists):
            self.store._ingredient_edit(self.onion_id, {},
                                        dict(name='Bell Pepper'))

        saved = self.driver.read(Ingredient,
                                 [{
                                     Ingredient.fields.id: self.onion_id
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Ingredient.fields.id: self.onion_id,
                Ingredient.fields.name: "Onion",
                Ingredient.fields.simple_name: "onion",
            },
        )

    def test_label_create(self):
        self.store._label_create({}, dict(name='chicken', ))

        saved = self.driver.read(Label, [{Label.fields.name: 'chicken'}])
        self.assertEqual(len(saved), 1)
        self.assertEqual(
            saved[0],
            saved[0] | {
                Label.fields.name: 'chicken',
            },
        )

    def test_label_create_existing(self):
        with self.assertRaises(LabelAlreadyExists):
            self.store._label_create({}, dict(name='mexican'))

        saved = self.driver.read(
            Label,
            [{
                Label.fields.name: 'mexican'
            }],
            exact=True,
        )
        self.assertEqual(len(saved), 1)

    def test_label_create_junk_args(self):
        with self.assertRaises(InvalidQuery):
            self.store._label_create({}, dict(name='chicken', btw='junk'))

        saved = self.driver.read(
            Label,
            [{
                Label.fields.name: 'chicken'
            }],
            exact=True,
        )
        self.assertEqual(len(saved), 0)

    def test_label_lookup(self):
        lookup = self.store._label_lookup({}, {})
        for index in [{
                "id":
                "a38985fe971482b9c489e196ce9b4046b5755c12d7ff1729ff101558f3ee71b9",
                "name": "mexican",
        }, {
                "id":
                "473e7cd6c7ee532d7ee62322c6c3c019445bb965d7b3bc69554e6f31c6cd34de",
                "name": "drink",
        }, {
                "id":
                "464223c5d6a1b972bd9481123175ffbeaaeabc9aa259cd00f0e4040f37956f18",
                "name": "spicy",
        }, {
                "id":
                "33d30cbbb689b326006570b74f1dc42ae4c098e3b7e24e0441070b721b56a0e7",
                "name": "vegan",
        }]:
            self.assertIn(index, lookup)

    def test_label_lookup_filter_name(self):
        lookup = self.store._label_lookup(dict(name='exi'), {})
        self.assertListEqual(lookup, [{
            "id": self.mexican_id,
            "name": "mexican",
        }])

        lookup = self.store._label_lookup(dict(name='drin'), {})
        self.assertListEqual(lookup, [{
            "id": self.drink_id,
            "name": "drink",
        }])

    def test_label_lookup_junk_args(self):
        with self.assertRaises(InvalidQuery):
            self.store._label_lookup(dict(name='chicken', btw='junk'), {})

    def test_label_delete(self):
        self.store._label_delete(self.vegan_id, {}, {})

        saved = self.driver.read(
            Label,
            [{
                Label.fields.name: 'vegan'
            }],
            exact=True,
        )
        self.assertEqual(len(saved), 0)

    #TODO
    """
    def test_label_delete_in_use(self):
        with self.assertRaises(LabelInUse):
            self.store._label_delete(self.mexican_id, {}, {})

        saved = self.driver.read(
            Label,
            [{
                Label.fields.name: 'mexican'
            }],
            exact=True,
        )
        self.assertEqual(len(saved), 1)
    """

    def test_label_delete_bad_id(self):
        with self.assertRaises(LabelNotFound):
            self.store._label_delete('badid', {}, {})

        saved = self.driver.read(Label)
        self.assertEqual(len(saved), 4)

    def test_label_show(self):
        saved = self.store._label_show(self.mexican_id, {}, {})

        keys = {
            'id',
            'name',
            'tagged_recipes',
        }

        self.assertTrue(keys.issubset(set(saved)),
                        msg=f"{keys} not in {set(saved)}")

        self.assertEqual(
            saved,
            saved | {
                "id": self.mexican_id,
                "name": "mexican",
            },
        )

        self.assertEqual(len(saved['tagged_recipes']), 5)

    def test_label_show_bad_id(self):
        with self.assertRaises(LabelNotFound):
            self.store._label_show('badid', {}, {})

    def test_label_edit(self):
        saved = self.store._label_edit(self.mexican_id, {},
                                       dict(name='tex-mex'))
        """
        self.assertTrue({
            'id',
            'name',
        }.issubset(set(saved)))

        self.assertEqual(
            saved,
            saved | {
                "id": self.mexican_id,
                "name": "tex-mex",
            },
        )
        """

        saved = self.driver.read(Label, [{
            Label.fields.id: self.mexican_id,
        }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Label.fields.id: self.mexican_id,
                Label.fields.name: "tex-mex",
                Label.fields.simple_name: "tex-mex",
            },
        )

    def test_label_edit_bad_id(self):
        with self.assertRaises(LabelNotFound):
            self.store._label_edit('badid', {}, dict(name='junk'))

    def test_label_edit_junk_form(self):
        with self.assertRaises(InvalidQuery):
            self.store._label_edit(self.mexican_id, {},
                                   dict(
                                       name='junk',
                                       btw='something',
                                   ))

        saved = self.driver.read(Label, [{Label.fields.id: self.mexican_id}])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Label.fields.id: self.mexican_id,
                Label.fields.name: "mexican",
                Label.fields.simple_name: "mexican",
            },
        )

    def test_label_edit_existing_name(self):
        with self.assertRaises(LabelAlreadyExists):
            self.store._label_edit(self.mexican_id, {}, dict(name='spicy'))

        saved = self.driver.read(Label, [{Label.fields.id: self.mexican_id}])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Label.fields.id: self.mexican_id,
                Label.fields.name: "mexican",
                Label.fields.simple_name: "mexican",
            },
        )

    def test_dependency_create(self):
        self.store._dependency_add(self.fajitas_id, {}, {
            Dependency.fields.requisite.name: self.horchata_id,
            Dependency.fields.quantity.name: 'A glass',
        })

        saved = self.driver.read(Dependency,
                                 filters=[{
                                     Dependency.fields.requisite:
                                     self.horchata_id
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Dependency.fields.required_by: self.fajitas_id,
                Dependency.fields.requisite: self.horchata_id,
                Dependency.fields.quantity: 'A glass',
            },
        )

    def test_dependency_create_default_quantity(self):
        self.store._dependency_add(
            self.fajitas_id, {}, {
                Dependency.fields.requisite.name: self.horchata_id,
            })

        saved = self.driver.read(Dependency,
                                 filters=[{
                                     Dependency.fields.requisite:
                                     self.horchata_id
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Dependency.fields.required_by: self.fajitas_id,
                Dependency.fields.requisite: self.horchata_id,
                Dependency.fields.quantity: Dependency.fields.quantity.default,
            },
        )

    def test_dependency_create_bad_ids(self):
        with self.assertRaises(RecipeNotFound):
            self.store._dependency_add(
                "badid", {}, {
                    Dependency.fields.requisite.name: self.pico_de_gallo_id,
                })

        with self.assertRaises(RecipeNotFound):
            self.store._dependency_add(
                self.fajitas_id, {}, {
                    Dependency.fields.requisite.name: "badid",
                })

    def test_dependency_create_junk_args(self):
        with self.assertRaises(InvalidQuery):
            self.store._dependency_add(self.fajitas_id, {}, {
                Dependency.fields.requisite.name: self.pico_de_gallo_id,
                'btw': 'junk'
            })

    def test_dependency_edit_quantity(self):
        self.store._dependency_edit(self.fajitas_id, self.guacamole_id, {}, {
            Dependency.fields.quantity.name: '2 cups',
        })

        saved = self.driver.read(Dependency,
                                 filters=[{
                                     Dependency.fields.required_by:
                                     self.fajitas_id,
                                     Dependency.fields.requisite:
                                     self.guacamole_id,
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Dependency.fields.required_by: self.fajitas_id,
                Dependency.fields.requisite: self.guacamole_id,
                Dependency.fields.quantity: '2 cups',
                Dependency.fields.optional: False,
            },
        )

    def test_dependency_edit_optional(self):
        self.store._dependency_edit(self.fajitas_id, self.guacamole_id, {}, {
            Dependency.fields.optional.name: True,
        })

        saved = self.driver.read(Dependency,
                                 filters=[{
                                     Dependency.fields.required_by:
                                     self.fajitas_id,
                                     Dependency.fields.requisite:
                                     self.guacamole_id,
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Dependency.fields.required_by: self.fajitas_id,
                Dependency.fields.requisite: self.guacamole_id,
                Dependency.fields.quantity: '1 cup',
                Dependency.fields.optional: True,
            },
        )

    def test_dependency_edit_bad_ids(self):
        with self.assertRaises(DependencyNotFound):
            self.store._dependency_edit(
                "badid", self.pico_de_gallo_id, {}, {
                    Dependency.fields.quantity.name: '2 cups',
                })

        with self.assertRaises(DependencyNotFound):
            self.store._dependency_edit(
                self.fajitas_id, "badid", {}, {
                    Dependency.fields.quantity.name: '2 cups',
                })

    def test_dependency_edit_junk_args(self):
        with self.assertRaises(InvalidQuery):
            self.store._dependency_edit(
                self.fajitas_id, self.guacamole_id, {}, {
                    Dependency.fields.quantity.name: '3 cups',
                    'btw': 'junk'
                })

        saved = self.driver.read(Dependency,
                                 filters=[{
                                     Dependency.fields.required_by:
                                     self.fajitas_id,
                                     Dependency.fields.requisite:
                                     self.guacamole_id,
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Dependency.fields.required_by: self.fajitas_id,
                Dependency.fields.requisite: self.guacamole_id,
                Dependency.fields.quantity: '1 cup',
            },
        )

    def test_dependency_delete(self):
        self.store._dependency_delete(self.fajitas_id, self.guacamole_id, {},
                                      {})

        saved = self.driver.read(Dependency,
                                 filters=[{
                                     Dependency.fields.required_by:
                                     self.fajitas_id,
                                     Dependency.fields.requisite:
                                     self.guacamole_id,
                                 }])
        self.assertEqual(len(saved), 0)

    def test_dependency_delete_bad_ids(self):
        with self.assertRaises(DependencyNotFound):
            self.store._dependency_delete(
                "badid", self.pico_de_gallo_id, {}, {
                    Dependency.fields.quantity.name: '2 cups',
                })

        with self.assertRaises(DependencyNotFound):
            self.store._dependency_delete(
                self.fajitas_id, "badid", {}, {
                    Dependency.fields.quantity.name: '2 cups',
                })

    def test_requirement_create(self):
        self.store._requirement_add(
            self.fajitas_id, {}, {
                Requirement.fields.ingredient_id.name: self.serrano_id,
                Requirement.fields.quantity.name: 'A smidge',
            })

        saved = self.driver.read(Requirement,
                                 filters=[{
                                     Requirement.fields.recipe_id:
                                     self.fajitas_id,
                                     Requirement.fields.ingredient_id:
                                     self.serrano_id
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Requirement.fields.recipe_id: self.fajitas_id,
                Requirement.fields.ingredient_id: self.serrano_id,
                Requirement.fields.quantity: 'A smidge',
            },
        )

    def test_requirement_create_bad_ids(self):
        with self.assertRaises(RecipeNotFound):
            self.store._requirement_add("badid", {}, {
                Requirement.fields.ingredient_id.name:
                self.pico_de_gallo_id,
            })

        with self.assertRaises(IngredientNotFound):
            self.store._requirement_add(
                self.fajitas_id, {}, {
                    Requirement.fields.ingredient_id.name: "badid",
                })

    def test_requirement_create_junk_args(self):
        with self.assertRaises(InvalidQuery):
            self.store._requirement_add(
                self.fajitas_id, {}, {
                    Requirement.fields.ingredient_id.name: self.serrano_id,
                    'btw': 'junk'
                })

        saved = self.driver.read(Requirement,
                                 filters=[{
                                     Requirement.fields.recipe_id:
                                     self.fajitas_id,
                                     Requirement.fields.ingredient_id:
                                     self.serrano_id,
                                 }])
        self.assertEqual(len(saved), 0)

    def test_requirement_edit_quantity(self):
        self.store._requirement_edit(
            self.fajitas_id, self.bell_pepper_id, {}, {
                Requirement.fields.quantity.name: '2 cups',
            })

        saved = self.driver.read(Requirement,
                                 filters=[{
                                     Requirement.fields.recipe_id:
                                     self.fajitas_id,
                                     Requirement.fields.ingredient_id:
                                     self.bell_pepper_id,
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Requirement.fields.recipe_id: self.fajitas_id,
                Requirement.fields.ingredient_id: self.bell_pepper_id,
                Requirement.fields.quantity: '2 cups',
                Requirement.fields.optional: False,
            },
        )

    def test_requirement_edit_optional(self):
        self.store._requirement_edit(
            self.fajitas_id, self.bell_pepper_id, {}, {
                Requirement.fields.optional.name: True,
            })

        saved = self.driver.read(Requirement,
                                 filters=[{
                                     Requirement.fields.recipe_id:
                                     self.fajitas_id,
                                     Requirement.fields.ingredient_id:
                                     self.bell_pepper_id,
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Requirement.fields.recipe_id: self.fajitas_id,
                Requirement.fields.ingredient_id: self.bell_pepper_id,
                Requirement.fields.quantity: '4',
                Requirement.fields.optional: True,
            },
        )

    def test_requirement_edit_bad_ids(self):
        with self.assertRaises(RequirementNotFound):
            self.store._requirement_edit(
                "badid", self.bell_pepper_id, {}, {
                    Requirement.fields.quantity.name: '2 cups',
                })

        with self.assertRaises(RequirementNotFound):
            self.store._requirement_edit(
                self.fajitas_id, "badid", {}, {
                    Requirement.fields.quantity.name: '2 cups',
                })

    def test_requirement_edit_junk_args(self):
        with self.assertRaises(InvalidQuery):
            self.store._requirement_edit(
                self.fajitas_id, self.bell_pepper_id, {}, {
                    Requirement.fields.quantity.name: '3 cups',
                    'btw': 'junk'
                })

        saved = self.driver.read(Requirement,
                                 filters=[{
                                     Requirement.fields.recipe_id:
                                     self.fajitas_id,
                                     Requirement.fields.ingredient_id:
                                     self.bell_pepper_id,
                                 }])
        self.assertEqual(len(saved), 1)

        self.assertEqual(
            saved[0],
            saved[0] | {
                Requirement.fields.recipe_id: self.fajitas_id,
                Requirement.fields.ingredient_id: self.bell_pepper_id,
                Requirement.fields.quantity: '4',
            },
        )

    def test_requirement_delete(self):
        self.store._requirement_delete(self.fajitas_id, self.bell_pepper_id,
                                       {}, {})

        saved = self.driver.read(Requirement,
                                 filters=[{
                                     Requirement.fields.recipe_id:
                                     self.fajitas_id,
                                     Requirement.fields.ingredient_id:
                                     self.bell_pepper_id,
                                 }])
        self.assertEqual(len(saved), 0)

    def test_requirement_delete_bad_ids(self):
        with self.assertRaises(RequirementNotFound):
            self.store._requirement_delete("badid", self.bell_pepper_id, {},
                                           {})

        with self.assertRaises(RequirementNotFound):
            self.store._requirement_delete(self.fajitas_id, "badid", {}, {})

    def test_tag_create(self):
        self.store._tag_add(self.fajitas_id, {}, {
            Label.fields.name.name: 'fast-food',
        })

        saved = self.driver.read(Tag,
                                 filters=[{
                                     Tag.fields.recipe_id:
                                     self.fajitas_id,
                                 }])
        self.assertEqual(len(saved), 2)

    def test_tag_create_bad_ids(self):
        with self.assertRaises(RecipeNotFound):
            self.store._tag_add("badid", {}, {
                Label.fields.name.name: 'test',
            })

    def test_tag_create_junk_args(self):
        with self.assertRaises(InvalidQuery):
            self.store._tag_add(self.fajitas_id, {}, {
                Label.fields.name.name: 'test',
                'btw': 'junk'
            })

        saved = self.driver.read(Tag,
                                 filters=[{
                                     Tag.fields.recipe_id:
                                     self.fajitas_id,
                                 }])
        self.assertEqual(len(saved), 1)

    def test_tag_delete(self):
        self.store._tag_delete(self.fajitas_id, self.mexican_id, {}, {})

        saved = self.driver.read(Tag,
                                 filters=[{
                                     Tag.fields.recipe_id:
                                     self.fajitas_id,
                                 }])
        self.assertEqual(len(saved), 0)

    def test_tag_delete_bad_ids(self):
        with self.assertRaises(TagNotFound):
            self.store._tag_delete("badid", self.mexican_id, {}, {})

        with self.assertRaises(TagNotFound):
            self.store._tag_delete(self.fajitas_id, "badid", {}, {})
