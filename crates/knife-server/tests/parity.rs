//! The v0.3 HTTP suite (`test/api/*.py`), ported to the new API. Each test
//! keeps the name of the Python test it replaces, in a module named after its
//! file. Where the expected outcome changed on purpose, a `Changed:` comment
//! says why. Run from the repo root, with every other emulator test:
//!
//! ```sh
//! firebase emulators:exec --only auth,firestore "cargo emulator-test"
//! ```

mod common;

use axum::http::StatusCode as Status;
use common::{Client, expect, nonce};
use serde_json::{Value, json};

macro_rules! scenario {
    ($name:ident, |$client:ident, $n:ident| $body:block) => {
        #[tokio::test]
        #[ignore = "needs the Firestore emulator"]
        async fn $name() {
            let $client = Client::new().await;
            let $n = nonce();
            let _ = &$n;
            $body
        }
    };
}

fn len(list: &Value) -> usize {
    list.as_array().expect("a list").len()
}

mod test_request_ingredients {
    use super::*;

    async fn oignon(client: &Client, n: &str) -> String {
        client
            .ingredient(json!({ "name": format!("Oignon {n}") }))
            .await
    }

    scenario!(test_index_all, |client, n| {
        let list = expect(client.get("/api/ingredients").await, Status::OK);
        assert!(list.is_array());
    });

    // Changed: lookups take only `prefix`; searching by id is gone.
    scenario!(test_index_id_search, |client, n| {
        expect(
            client.get("/api/ingredients?id=test").await,
            Status::BAD_REQUEST,
        );
    });

    // Changed: `name` became `prefix`, matched on the simple name.
    scenario!(test_index_name_search, |client, n| {
        oignon(&client, &n).await;
        let list = expect(
            client
                .get(&format!("/api/ingredients?prefix=Oignon%20{n}"))
                .await,
            Status::OK,
        );
        assert_eq!(len(&list), 1);
    });

    // Changed: `id` is no longer a filter, so mixing it in is rejected.
    scenario!(test_index_mixed_search, |client, n| {
        expect(
            client.get("/api/ingredients?id=hex&prefix=oignon").await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_index_wrong_field_search, |client, n| {
        expect(
            client.get("/api/ingredients?wrong_field=Oignon").await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_index_wrong_mixed_search, |client, n| {
        expect(
            client
                .get("/api/ingredients?prefix=Oignon&wrong_field=stuff")
                .await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_create_name, |client, n| {
        let created = expect(
            client
                .post("/api/ingredients", json!({ "name": format!("Oignon {n}") }))
                .await,
            Status::CREATED,
        );
        assert!(created["id"].is_string());
    });

    scenario!(test_create_no_name, |client, n| {
        expect(
            client.post("/api/ingredients", json!({})).await,
            Status::UNPROCESSABLE_ENTITY,
        );
    });

    scenario!(test_create_same, |client, n| {
        oignon(&client, &n).await;
        expect(
            client
                .post("/api/ingredients", json!({ "name": format!("Oignon {n}") }))
                .await,
            Status::CONFLICT,
        );
    });

    scenario!(test_create_wrong_params, |client, n| {
        expect(
            client
                .post(
                    "/api/ingredients",
                    json!({ "name": format!("Oignon {n}"), "metadata": "stuff" }),
                )
                .await,
            Status::UNPROCESSABLE_ENTITY,
        );
    });

    scenario!(test_create_empty, |client, n| {
        expect(
            client.post("/api/ingredients", json!({ "name": "" })).await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_delete, |client, n| {
        let id = oignon(&client, &n).await;
        expect(
            client.delete(&format!("/api/ingredients/{id}")).await,
            Status::NO_CONTENT,
        );
    });

    scenario!(test_delete_nonexistent, |client, n| {
        let id = oignon(&client, &n).await;
        client.delete(&format!("/api/ingredients/{id}")).await;
        expect(
            client.delete(&format!("/api/ingredients/{id}")).await,
            Status::NOT_FOUND,
        );
    });

    scenario!(test_edit_name, |client, n| {
        let id = oignon(&client, &n).await;
        let new_name = format!("Oignon Francais {n}");
        expect(
            client
                .patch(
                    &format!("/api/ingredients/{id}"),
                    json!({ "name": new_name }),
                )
                .await,
            Status::OK,
        );

        let list = expect(
            client
                .get(&format!("/api/ingredients?prefix=oignon_francais_{n}"))
                .await,
            Status::OK,
        );
        assert_eq!(list[0]["name"], new_name);
    });

    scenario!(test_edit_name_invalid, |client, n| {
        let id = oignon(&client, &n).await;
        let uri = format!("/api/ingredients/{id}");
        expect(
            client.patch(&uri, json!({ "name": "" })).await,
            Status::BAD_REQUEST,
        );
        let shown = expect(client.get(&uri).await, Status::OK);
        assert_eq!(shown["name"], format!("Oignon {n}"));
    });

    scenario!(test_edit_name_taken, |client, n| {
        let id = oignon(&client, &n).await;
        let new_name = format!("Oignon Francais {n}");
        client.ingredient(json!({ "name": new_name })).await;

        let uri = format!("/api/ingredients/{id}");
        expect(
            client.patch(&uri, json!({ "name": new_name })).await,
            Status::CONFLICT,
        );
        let shown = expect(client.get(&uri).await, Status::OK);
        assert_eq!(shown["name"], format!("Oignon {n}"));
    });

    scenario!(test_edit_nonexistent, |client, n| {
        let id = oignon(&client, &n).await;
        expect(
            client
                .patch(
                    &format!("/api/ingredients/{id}_bis"),
                    json!({ "name": format!("Oignon Francais {n}") }),
                )
                .await,
            Status::NOT_FOUND,
        );
    });
}

/// Changed throughout: labels are created by tagging a recipe; there is no
/// `POST /labels` and no label without recipes. Labels are addressed by
/// simple name instead of an id.
mod test_request_labels {
    use super::*;

    /// Tag a new recipe with `label` and return the label's simple name.
    async fn tagged(client: &Client, n: &str, label: &str) -> String {
        let recipe = client.recipe(&format!("Tartare {label} {n}")).await;
        let recipe = expect(
            client
                .put(&format!("/api/recipes/{recipe}/tags/{label}"), json!(null))
                .await,
            Status::OK,
        );
        recipe["tags"][0].as_str().unwrap().to_owned()
    }

    scenario!(test_index_all, |client, n| {
        let list = expect(client.get("/api/labels").await, Status::OK);
        assert!(list.is_array());
    });

    // Changed: lookups take only `prefix`.
    scenario!(test_index_id_search, |client, n| {
        expect(client.get("/api/labels?id=test").await, Status::BAD_REQUEST);
    });

    scenario!(test_index_name_search, |client, n| {
        let label = tagged(&client, &n, &format!("french{n}")).await;
        let list = expect(
            client.get(&format!("/api/labels?prefix={label}")).await,
            Status::OK,
        );
        assert_eq!(len(&list), 1);
    });

    // Changed: `id` is no longer a filter.
    scenario!(test_index_mixed_search, |client, n| {
        expect(
            client.get("/api/labels?id=hex&prefix=french").await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_index_wrong_field_search, |client, n| {
        expect(
            client.get("/api/labels?wrong_field=french").await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_index_wrong_mixed_search, |client, n| {
        expect(
            client
                .get("/api/labels?prefix=french&wrong_field=stuff")
                .await,
            Status::BAD_REQUEST,
        );
    });

    // Changed: created by tagging.
    scenario!(test_create_name, |client, n| {
        let label = tagged(&client, &n, &format!("french{n}")).await;
        let shown = expect(
            client.get(&format!("/api/labels/{label}")).await,
            Status::OK,
        );
        assert_eq!(shown["recipe_count"], 1);
    });

    // Changed: the name is in the path; a blank one is rejected.
    scenario!(test_create_no_name, |client, n| {
        let recipe = client.recipe(&format!("Tartare {n}")).await;
        expect(
            client
                .put(&format!("/api/recipes/{recipe}/tags/%20"), json!(null))
                .await,
            Status::BAD_REQUEST,
        );
    });

    // Changed: tagging another recipe with an existing label reuses it
    // instead of failing.
    scenario!(test_create_same, |client, n| {
        let label = format!("french{n}");
        tagged(&client, &n, &label).await;
        let other = client.recipe(&format!("Frites {n}")).await;
        expect(
            client
                .put(&format!("/api/recipes/{other}/tags/{label}"), json!(null))
                .await,
            Status::OK,
        );

        let list = expect(
            client.get(&format!("/api/labels?prefix={label}")).await,
            Status::OK,
        );
        assert_eq!(len(&list), 1);
        assert_eq!(list[0]["recipe_count"], 2);
    });

    // Changed: the tag route takes no body, so there are no extra fields to
    // reject. Unknown fields on the label rename are rejected instead.
    scenario!(test_create_wrong_params, |client, n| {
        let label = tagged(&client, &n, &format!("french{n}")).await;
        expect(
            client
                .patch(
                    &format!("/api/labels/{label}"),
                    json!({ "name": "francais", "metadata": "stuff" }),
                )
                .await,
            Status::UNPROCESSABLE_ENTITY,
        );
    });

    scenario!(test_create_empty, |client, n| {
        let recipe = client.recipe(&format!("Tartare {n}")).await;
        expect(
            client
                .put(&format!("/api/recipes/{recipe}/tags/%20%20"), json!(null))
                .await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_delete, |client, n| {
        let label = tagged(&client, &n, &format!("french{n}")).await;
        expect(
            client.delete(&format!("/api/labels/{label}")).await,
            Status::NO_CONTENT,
        );
    });

    scenario!(test_delete_nonexistent, |client, n| {
        let label = tagged(&client, &n, &format!("french{n}")).await;
        client.delete(&format!("/api/labels/{label}")).await;
        expect(
            client.delete(&format!("/api/labels/{label}")).await,
            Status::NOT_FOUND,
        );
    });

    scenario!(test_edit_name, |client, n| {
        let label = tagged(&client, &n, &format!("french{n}")).await;
        let new_name = format!("francais{n}");
        expect(
            client
                .patch(&format!("/api/labels/{label}"), json!({ "name": new_name }))
                .await,
            Status::OK,
        );

        let list = expect(
            client.get(&format!("/api/labels?prefix={new_name}")).await,
            Status::OK,
        );
        assert_eq!(list[0]["name"], new_name);
    });

    scenario!(test_edit_name_invalid, |client, n| {
        let label = tagged(&client, &n, &format!("french{n}")).await;
        let uri = format!("/api/labels/{label}");
        expect(
            client.patch(&uri, json!({ "name": "" })).await,
            Status::BAD_REQUEST,
        );
        let shown = expect(client.get(&uri).await, Status::OK);
        assert_eq!(shown["name"], label);

        expect(
            client
                .patch(&uri, json!({ "name": "name with space" }))
                .await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_edit_name_taken, |client, n| {
        let label = tagged(&client, &n, &format!("french{n}")).await;
        let taken = format!("français{n}");
        tagged(&client, &n, &taken).await;

        let uri = format!("/api/labels/{label}");
        expect(
            client.patch(&uri, json!({ "name": taken })).await,
            Status::CONFLICT,
        );
        let shown = expect(client.get(&uri).await, Status::OK);
        assert_eq!(shown["name"], label);
    });

    scenario!(test_edit_nonexistent, |client, n| {
        let label = tagged(&client, &n, &format!("french{n}")).await;
        expect(
            client
                .patch(
                    &format!("/api/labels/{label}_bis"),
                    json!({ "name": "Francais" }),
                )
                .await,
            Status::NOT_FOUND,
        );
    });
}

mod test_request_recipes {
    use super::*;

    async fn tartare(client: &Client, n: &str) -> String {
        client.recipe(&format!("Tartare {n}")).await
    }

    scenario!(test_index_all, |client, n| {
        let list = expect(client.get("/api/recipes").await, Status::OK);
        assert!(list.is_array());
    });

    // Changed: lookups take only `prefix`.
    scenario!(test_index_id_search, |client, n| {
        expect(
            client.get("/api/recipes?id=test").await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_index_name_search, |client, n| {
        tartare(&client, &n).await;
        let list = expect(
            client
                .get(&format!("/api/recipes?prefix=Tartare%20{n}"))
                .await,
            Status::OK,
        );
        assert_eq!(len(&list), 1);
    });

    // Changed: authors are not searchable; lookups take only `prefix`.
    scenario!(test_index_author_search, |client, n| {
        expect(
            client.get("/api/recipes?author=jb").await,
            Status::BAD_REQUEST,
        );
    });

    // Changed: directions are not searchable; Firestore has no substring
    // search.
    scenario!(test_index_directions_search, |client, n| {
        expect(
            client.get("/api/recipes?directions=do%20stuff").await,
            Status::BAD_REQUEST,
        );
    });

    // Changed: `author` is not a filter; lookups take only `prefix`.
    scenario!(test_index_mixed_search, |client, n| {
        expect(
            client.get("/api/recipes?author=jb&prefix=Tartare").await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_index_wrong_field_search, |client, n| {
        expect(
            client.get("/api/recipes?wrong_field=Tartare").await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_index_wrong_mixed_search, |client, n| {
        expect(
            client
                .get("/api/recipes?prefix=Tartare&wrong_field=jb")
                .await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_create_name, |client, n| {
        let created = expect(
            client
                .post("/api/recipes", json!({ "name": format!("Tartare {n}") }))
                .await,
            Status::CREATED,
        );
        assert!(created["id"].is_string());
    });

    scenario!(test_create_full, |client, n| {
        let created = expect(
            client
                .post(
                    "/api/recipes",
                    json!({
                        "name": format!("Tartare {n}"),
                        "author": "jb",
                        "directions": "Do stuff",
                    }),
                )
                .await,
            Status::CREATED,
        );
        assert!(created["id"].is_string());
        assert_eq!(created["author"], "jb");
        // The family member who added it is recorded separately.
        assert_eq!(created["created_by"], common::UID);
    });

    scenario!(test_create_no_name, |client, n| {
        expect(
            client
                .post("/api/recipes", json!({ "directions": "Do stuff" }))
                .await,
            Status::UNPROCESSABLE_ENTITY,
        );
    });

    scenario!(test_create_same, |client, n| {
        tartare(&client, &n).await;
        expect(
            client
                .post("/api/recipes", json!({ "name": format!("Tartare {n}") }))
                .await,
            Status::CONFLICT,
        );
    });

    scenario!(test_create_wrong_params, |client, n| {
        expect(
            client
                .post(
                    "/api/recipes",
                    json!({
                        "name": format!("Tartare {n}"),
                        "directions": "Do stuff",
                        "metadata": "stuff",
                    }),
                )
                .await,
            Status::UNPROCESSABLE_ENTITY,
        );
    });

    scenario!(test_create_empty, |client, n| {
        expect(
            client.post("/api/recipes", json!({ "name": "" })).await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_delete, |client, n| {
        let id = tartare(&client, &n).await;
        expect(
            client.delete(&format!("/api/recipes/{id}")).await,
            Status::NO_CONTENT,
        );
    });

    scenario!(test_delete_nonexistent, |client, n| {
        let id = tartare(&client, &n).await;
        client.delete(&format!("/api/recipes/{id}")).await;
        expect(
            client.delete(&format!("/api/recipes/{id}")).await,
            Status::NOT_FOUND,
        );
    });

    scenario!(test_edit_name, |client, n| {
        let id = tartare(&client, &n).await;
        let uri = format!("/api/recipes/{id}");
        let new_name = format!("Tartare Francais {n}");
        expect(
            client.patch(&uri, json!({ "name": new_name })).await,
            Status::OK,
        );
        let shown = expect(client.get(&uri).await, Status::OK);
        assert_eq!(shown["name"], new_name);
    });

    scenario!(test_edit_author, |client, n| {
        let id = tartare(&client, &n).await;
        let uri = format!("/api/recipes/{id}");
        expect(
            client.patch(&uri, json!({ "author": "jb" })).await,
            Status::OK,
        );
        let shown = expect(client.get(&uri).await, Status::OK);
        assert_eq!(shown["author"], "jb");
        assert_eq!(shown["created_by"], common::UID);
    });

    scenario!(test_edit_directions, |client, n| {
        let id = tartare(&client, &n).await;
        let uri = format!("/api/recipes/{id}");
        expect(
            client
                .patch(&uri, json!({ "directions": "do stuff" }))
                .await,
            Status::OK,
        );
        let shown = expect(client.get(&uri).await, Status::OK);
        assert_eq!(shown["directions"], "do stuff");
    });

    scenario!(test_edit_mixed, |client, n| {
        let id = tartare(&client, &n).await;
        let uri = format!("/api/recipes/{id}");
        let new_name = format!("Super Tartare {n}");
        expect(
            client
                .patch(
                    &uri,
                    json!({
                        "name": new_name,
                        "directions": "do stuff",
                        "author": "jb",
                    }),
                )
                .await,
            Status::OK,
        );
        let shown = expect(client.get(&uri).await, Status::OK);
        assert_eq!(shown["name"], new_name);
        assert_eq!(shown["directions"], "do stuff");
        assert_eq!(shown["author"], "jb");
    });

    scenario!(test_edit_name_invalid, |client, n| {
        let id = tartare(&client, &n).await;
        let uri = format!("/api/recipes/{id}");
        expect(
            client.patch(&uri, json!({ "name": "" })).await,
            Status::BAD_REQUEST,
        );
        let shown = expect(client.get(&uri).await, Status::OK);
        assert_eq!(shown["name"], format!("Tartare {n}"));
    });

    scenario!(test_edit_same_name, |client, n| {
        let id = tartare(&client, &n).await;
        let uri = format!("/api/recipes/{id}");
        expect(
            client
                .patch(
                    &uri,
                    json!({ "name": format!("Tartare {n}"), "author": "dark jb" }),
                )
                .await,
            Status::OK,
        );
        let shown = expect(client.get(&uri).await, Status::OK);
        assert_eq!(shown["name"], format!("Tartare {n}"));
        assert_eq!(shown["author"], "dark jb");
    });

    scenario!(test_edit_name_taken, |client, n| {
        let id = tartare(&client, &n).await;
        let new_name = format!("Tartare Francais {n}");
        client.recipe(&new_name).await;

        let uri = format!("/api/recipes/{id}");
        expect(
            client.patch(&uri, json!({ "name": new_name })).await,
            Status::CONFLICT,
        );
        let shown = expect(client.get(&uri).await, Status::OK);
        assert_eq!(shown["name"], format!("Tartare {n}"));
    });

    scenario!(test_edit_nonexistent, |client, n| {
        let id = tartare(&client, &n).await;
        expect(
            client
                .patch(
                    &format!("/api/recipes/{id}_bis"),
                    json!({ "name": format!("Tartare Francais {n}") }),
                )
                .await,
            Status::NOT_FOUND,
        );
    });

    // Changed: `information`, `classification` and `created_by` are new.
    scenario!(test_show_fields, |client, n| {
        let id = tartare(&client, &n).await;
        let shown = expect(client.get(&format!("/api/recipes/{id}")).await, Status::OK);
        for field in [
            "id",
            "name",
            "author",
            "directions",
            "information",
            "requirements",
            "tags",
            "dependencies",
            "classification",
            "created_by",
        ] {
            assert!(shown.get(field).is_some(), "missing {field}: {shown}");
        }
    });

    scenario!(test_show_nonexistent, |client, n| {
        let id = tartare(&client, &n).await;
        expect(
            client.get(&format!("/api/recipes/{id}_bis")).await,
            Status::NOT_FOUND,
        );
    });
}

/// Changed throughout: requirements are listed in `GET /recipes/{id}` and
/// written with `PUT /recipes/{id}/requirements/{ingredient_id}`, which adds
/// or replaces.
mod test_request_requirements {
    use super::*;

    struct Fixture {
        recipe: String,
        ingredients: [String; 2],
    }

    impl Fixture {
        /// A recipe and two ingredients, the first required with quantity 4.
        async fn new(client: &Client, n: &str) -> Self {
            let recipe = client.recipe(&format!("Tartare {n}")).await;
            let oignon = client
                .ingredient(json!({ "name": format!("Oignon {n}") }))
                .await;
            let cornichon = client
                .ingredient(json!({ "name": format!("Cornichon {n}") }))
                .await;

            let fixture = Self {
                recipe,
                ingredients: [oignon, cornichon],
            };
            expect(
                client.put(&fixture.uri(0), json!({ "quantity": 4 })).await,
                Status::OK,
            );
            fixture
        }

        fn uri(&self, ingredient: usize) -> String {
            self.uri_for(&self.ingredients[ingredient])
        }

        fn uri_for(&self, ingredient: &str) -> String {
            format!("/api/recipes/{}/requirements/{ingredient}", self.recipe)
        }

        async fn requirements(&self, client: &Client) -> Value {
            let recipe = expect(
                client.get(&format!("/api/recipes/{}", self.recipe)).await,
                Status::OK,
            );
            recipe["requirements"].clone()
        }

        async fn quantity(&self, client: &Client) -> Value {
            self.requirements(client).await[&self.ingredients[0]]["quantity"].clone()
        }
    }

    scenario!(test_index_all, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        let requirements = fixture.requirements(&client).await;
        assert_eq!(requirements.as_object().unwrap().len(), 1);
        assert_eq!(fixture.quantity(&client).await, "4");
    });

    scenario!(test_add, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(
            client.put(&fixture.uri(1), json!({ "quantity": 3 })).await,
            Status::OK,
        );
    });

    // Changed: the ingredient is in the path; an unknown one is a 404.
    scenario!(test_add_no_ingredient, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(
            client
                .put(&fixture.uri_for("nonexistent"), json!({ "quantity": 3 }))
                .await,
            Status::NOT_FOUND,
        );
    });

    scenario!(test_add_no_quantity, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(
            client.put(&fixture.uri(1), json!({})).await,
            Status::UNPROCESSABLE_ENTITY,
        );
    });

    // Changed: PUT replaces an existing requirement instead of failing.
    scenario!(test_add_same, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(
            client.put(&fixture.uri(0), json!({ "quantity": 3 })).await,
            Status::OK,
        );
        assert_eq!(fixture.quantity(&client).await, "3");
    });

    scenario!(test_add_wrong_ingredient, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(
            client
                .put(&fixture.uri_for("Nonexistent"), json!({ "quantity": 3 }))
                .await,
            Status::NOT_FOUND,
        );
    });

    scenario!(test_add_wrong_params, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(
            client
                .put(&fixture.uri(1), json!({ "quantity": 3, "metadata": "lol" }))
                .await,
            Status::UNPROCESSABLE_ENTITY,
        );
    });

    scenario!(test_create_empty, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(
            client
                .put(
                    &fixture.uri(1),
                    json!({ "quantity": null, "metadata": "lol" }),
                )
                .await,
            Status::UNPROCESSABLE_ENTITY,
        );
    });

    scenario!(test_delete, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(client.delete(&fixture.uri(0)).await, Status::OK);
        assert_eq!(fixture.requirements(&client).await, json!({}));
    });

    scenario!(test_delete_nonexistent, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(
            client.delete(&fixture.uri_for("nonexistent")).await,
            Status::NOT_FOUND,
        );
    });

    scenario!(test_edit, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(
            client
                .put(&fixture.uri(0), json!({ "quantity": "5 cups" }))
                .await,
            Status::OK,
        );
        assert_eq!(fixture.quantity(&client).await, "5 cups");
    });

    scenario!(test_edit_nonexistent, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(
            client
                .put(&fixture.uri_for("nonexistent"), json!({ "quantity": 5 }))
                .await,
            Status::NOT_FOUND,
        );
    });

    scenario!(test_edit_invalid_quantity, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(
            client.put(&fixture.uri(0), json!({ "quantity": "" })).await,
            Status::BAD_REQUEST,
        );
        assert_eq!(fixture.quantity(&client).await, "4");
    });

    scenario!(test_edit_wrong_field, |client, n| {
        let fixture = Fixture::new(&client, &n).await;
        expect(
            client
                .put(&fixture.uri(0), json!({ "quantitad": "5 cups" }))
                .await,
            Status::UNPROCESSABLE_ENTITY,
        );
        expect(
            client
                .put(
                    &fixture.uri(0),
                    json!({ "quantity": "5 cups", "metadata": false }),
                )
                .await,
            Status::UNPROCESSABLE_ENTITY,
        );
        assert_eq!(fixture.quantity(&client).await, "4");
    });
}

/// Changed throughout: dependencies are listed in `GET /recipes/{id}` and
/// written with `PUT /recipes/{id}/dependencies/{requisite_id}`, which adds or
/// replaces.
mod test_request_dependencies {
    use super::*;

    /// Tartare and Frites; nothing depends on anything yet.
    async fn recipes(client: &Client, n: &str) -> (String, String) {
        (
            client.recipe(&format!("Tartare {n}")).await,
            client.recipe(&format!("Frites {n}")).await,
        )
    }

    fn uri(recipe: &str, requisite: &str) -> String {
        format!("/api/recipes/{recipe}/dependencies/{requisite}")
    }

    async fn dependency(client: &Client, recipe: &str, requisite: &str) -> Value {
        let shown = expect(
            client.get(&format!("/api/recipes/{recipe}")).await,
            Status::OK,
        );
        shown["dependencies"][requisite].clone()
    }

    scenario!(test_index_all, |client, n| {
        let (tartare, frites) = recipes(&client, &n).await;
        expect(
            client.put(&uri(&tartare, &frites), json!({})).await,
            Status::OK,
        );

        let shown = expect(
            client.get(&format!("/api/recipes/{tartare}")).await,
            Status::OK,
        );
        assert_eq!(shown["dependencies"].as_object().unwrap().len(), 1);
    });

    scenario!(test_add, |client, n| {
        let (tartare, frites) = recipes(&client, &n).await;
        expect(
            client.put(&uri(&tartare, &frites), json!({})).await,
            Status::OK,
        );
    });

    // Changed: the requisite is in the path; an unknown one is a 404.
    scenario!(test_add_no_recipe, |client, n| {
        let (tartare, _) = recipes(&client, &n).await;
        expect(
            client.put(&uri(&tartare, "nonexistent"), json!({})).await,
            Status::NOT_FOUND,
        );
    });

    // Changed: PUT replaces an existing dependency instead of failing.
    scenario!(test_add_same, |client, n| {
        let (tartare, frites) = recipes(&client, &n).await;
        client.put(&uri(&tartare, &frites), json!({})).await;
        expect(
            client
                .put(&uri(&tartare, &frites), json!({ "quantity": "2" }))
                .await,
            Status::OK,
        );
        assert_eq!(
            dependency(&client, &tartare, &frites).await["quantity"],
            "2"
        );
    });

    scenario!(test_add_wrong_field, |client, n| {
        let (tartare, frites) = recipes(&client, &n).await;
        expect(
            client
                .put(
                    &uri(&tartare, &frites),
                    json!({ "ingredient": "Nonexistent" }),
                )
                .await,
            Status::UNPROCESSABLE_ENTITY,
        );
    });

    scenario!(test_add_invalid_recipe, |client, n| {
        let (tartare, _) = recipes(&client, &n).await;
        expect(
            client.put(&uri(&tartare, "nonexistent"), json!({})).await,
            Status::NOT_FOUND,
        );
    });

    scenario!(test_add_cycle, |client, n| {
        let (tartare, frites) = recipes(&client, &n).await;
        expect(
            client.put(&uri(&tartare, &frites), json!({})).await,
            Status::OK,
        );
        expect(
            client.put(&uri(&frites, &tartare), json!({})).await,
            Status::CONFLICT,
        );
        // Changed: a recipe depending on itself is invalid input (400), not a
        // conflict.
        expect(
            client.put(&uri(&tartare, &tartare), json!({})).await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_edit_quantity, |client, n| {
        let (tartare, frites) = recipes(&client, &n).await;
        let uri = uri(&tartare, &frites);
        client.put(&uri, json!({ "quantity": "A ton" })).await;
        expect(
            client.put(&uri, json!({ "quantity": "some amount" })).await,
            Status::OK,
        );
        assert_eq!(
            dependency(&client, &tartare, &frites).await["quantity"],
            "some amount"
        );
    });

    // Changed: PUT replaces the whole dependency, so fields left out return
    // to their defaults.
    scenario!(test_edit_optional, |client, n| {
        let (tartare, frites) = recipes(&client, &n).await;
        let uri = uri(&tartare, &frites);
        client
            .put(&uri, json!({ "optional": true, "quantity": "1" }))
            .await;
        expect(
            client.put(&uri, json!({ "optional": false })).await,
            Status::OK,
        );
        assert_eq!(
            dependency(&client, &tartare, &frites).await,
            json!({ "name": format!("Frites {n}"), "quantity": "", "optional": false })
        );
    });

    scenario!(test_delete, |client, n| {
        let (tartare, frites) = recipes(&client, &n).await;
        client.put(&uri(&tartare, &frites), json!({})).await;
        expect(client.delete(&uri(&tartare, &frites)).await, Status::OK);
    });

    scenario!(test_delete_nonexistent, |client, n| {
        let (tartare, _) = recipes(&client, &n).await;
        expect(
            client.delete(&uri(&tartare, "nonexistent")).await,
            Status::NOT_FOUND,
        );
    });
}

/// Changed throughout: tags are listed in `GET /recipes/{id}` and written
/// with `PUT /recipes/{id}/tags/{label}`, naming the label in the path.
mod test_request_tags {
    use super::*;

    /// A recipe tagged `french{n}`; returns the recipe and the label.
    async fn tagged(client: &Client, n: &str) -> (String, String) {
        let recipe = client.recipe(&format!("Tartare {n}")).await;
        let label = format!("french{n}");
        expect(
            client.put(&uri(&recipe, &label), json!(null)).await,
            Status::OK,
        );
        (recipe, label)
    }

    fn uri(recipe: &str, label: &str) -> String {
        format!("/api/recipes/{recipe}/tags/{label}")
    }

    scenario!(test_index_all, |client, n| {
        let (recipe, label) = tagged(&client, &n).await;
        let shown = expect(
            client.get(&format!("/api/recipes/{recipe}")).await,
            Status::OK,
        );
        assert_eq!(shown["tags"], json!([label]));
    });

    scenario!(test_add, |client, n| {
        let (recipe, _) = tagged(&client, &n).await;
        expect(
            client
                .put(&uri(&recipe, &format!("sweet{n}")), json!(null))
                .await,
            Status::OK,
        );
    });

    scenario!(test_add_no_name, |client, n| {
        let (recipe, _) = tagged(&client, &n).await;
        expect(
            client.put(&uri(&recipe, "%20"), json!(null)).await,
            Status::BAD_REQUEST,
        );
    });

    // Changed: tagging twice is a no-op instead of a conflict.
    scenario!(test_add_same, |client, n| {
        let (recipe, label) = tagged(&client, &n).await;
        let shown = expect(
            client.put(&uri(&recipe, &label), json!(null)).await,
            Status::OK,
        );
        assert_eq!(shown["tags"], json!([label]));

        let label = expect(
            client.get(&format!("/api/labels/{label}")).await,
            Status::OK,
        );
        assert_eq!(label["recipe_count"], 1);
    });

    // Changed: the tag route takes no body; a label that is not a single
    // word is the closest invalid input.
    scenario!(test_add_wrong_field, |client, n| {
        let (recipe, _) = tagged(&client, &n).await;
        expect(
            client
                .put(&uri(&recipe, "Nonexistent%20ingredient"), json!(null))
                .await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_add_invalid_name, |client, n| {
        let (recipe, _) = tagged(&client, &n).await;
        expect(
            client.put(&uri(&recipe, "%20%20"), json!(null)).await,
            Status::BAD_REQUEST,
        );
    });

    scenario!(test_delete, |client, n| {
        let (recipe, label) = tagged(&client, &n).await;
        let shown = expect(client.delete(&uri(&recipe, &label)).await, Status::OK);
        assert_eq!(shown["tags"], json!([]));
    });

    scenario!(test_delete_nonexistent, |client, n| {
        let (recipe, _) = tagged(&client, &n).await;
        expect(
            client.delete(&uri(&recipe, "nonexistent")).await,
            Status::NOT_FOUND,
        );
    });
}
