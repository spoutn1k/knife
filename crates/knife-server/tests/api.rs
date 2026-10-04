//! The HTTP API against the Firestore emulator. Run from the repo root,
//! with every other emulator test:
//!
//! ```sh
//! firebase emulators:exec --only auth,firestore "cargo emulator-test"
//! ```

mod common;

use axum::body::Body;
use axum::http::{Request, StatusCode};
use common::{Client, UID, nonce};
use serde_json::{Value, json};
use tower::ServiceExt;

fn flags(dairy: bool, meat: bool) -> Value {
    json!({ "dairy": dairy, "meat": meat, "gluten": false, "animal_product": false })
}

#[tokio::test]
#[ignore = "needs the Firestore emulator"]
async fn ingredient_lifecycle() {
    let client = Client::new().await;
    let n = nonce();

    let (status, created) = client
        .post(
            "/api/ingredients",
            json!({ "name": format!("Crème {n}"), "dairy": true }),
        )
        .await;
    assert_eq!(status, StatusCode::CREATED, "{created}");
    assert_eq!(created["simple_name"], format!("creme_{n}"));
    assert_eq!(created["classification"]["dairy"], true);
    let id = created["id"].as_str().unwrap();

    // Same simple name: conflict naming the existing ingredient.
    let (status, conflict) = client
        .post("/api/ingredients", json!({ "name": format!("creme {n}") }))
        .await;
    assert_eq!(status, StatusCode::CONFLICT);
    assert_eq!(conflict["existing"]["id"], id);

    let (status, listed) = client
        .get(&format!("/api/ingredients?prefix=CREME%20{n}"))
        .await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(listed, json!([{ "id": id, "name": format!("Crème {n}") }]));

    let (status, shown) = client.get(&format!("/api/ingredients/{id}")).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(shown["used_in"], json!([]));

    let (status, renamed) = client
        .patch(
            &format!("/api/ingredients/{id}"),
            json!({ "name": format!("Cream {n}") }),
        )
        .await;
    assert_eq!(status, StatusCode::OK, "{renamed}");
    assert_eq!(renamed["simple_name"], format!("cream_{n}"));
    assert_eq!(renamed["classification"]["dairy"], true);

    // The old name is free again.
    let other = client
        .ingredient(json!({ "name": format!("Crème {n}") }))
        .await;
    assert_ne!(other, id);

    let (status, _) = client.delete(&format!("/api/ingredients/{id}")).await;
    assert_eq!(status, StatusCode::NO_CONTENT);
    let (status, _) = client.get(&format!("/api/ingredients/{id}")).await;
    assert_eq!(status, StatusCode::NOT_FOUND);
}

#[tokio::test]
#[ignore = "needs the Firestore emulator"]
async fn bodies_are_validated() {
    let client = Client::new().await;
    let id = client
        .ingredient(json!({ "name": format!("Salt {}", nonce()) }))
        .await;
    let uri = format!("/api/ingredients/{id}");

    let (status, _) = client.patch(&uri, json!({ "dairy": "yes" })).await;
    assert_eq!(status, StatusCode::UNPROCESSABLE_ENTITY);

    let (status, _) = client.patch(&uri, json!({ "color": "white" })).await;
    assert_eq!(status, StatusCode::UNPROCESSABLE_ENTITY);

    let (status, problem) = client.patch(&uri, json!({})).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    assert_eq!(problem["status"], 400);

    let (status, _) = client
        .post("/api/ingredients", json!({ "name": "  " }))
        .await;
    assert_eq!(status, StatusCode::BAD_REQUEST);

    let (status, _) = client.get("/api/ingredients?name=salt").await;
    assert_eq!(status, StatusCode::BAD_REQUEST);

    // A body that is not JSON.
    let request = Request::post("/api/recipes")
        .header("Authorization", format!("Bearer {}", client.token))
        .header("Content-Type", "application/x-www-form-urlencoded")
        .body(Body::from("name=Pie"))
        .unwrap();
    let response = client.app.clone().oneshot(request).await.unwrap();
    assert_eq!(response.status(), StatusCode::UNSUPPORTED_MEDIA_TYPE);
}

#[tokio::test]
#[ignore = "needs the Firestore emulator"]
async fn recipe_lifecycle() {
    let client = Client::new().await;
    let n = nonce();

    let (status, created) = client
        .post(
            "/api/recipes",
            json!({ "name": format!("Quiche {n}"), "directions": "Bake" }),
        )
        .await;
    assert_eq!(status, StatusCode::CREATED, "{created}");
    assert_eq!(created["created_by"], UID);
    assert_eq!(created["directions"], "Bake");
    let id = created["id"].as_str().unwrap();

    let (status, _) = client
        .post("/api/recipes", json!({ "name": format!("QUICHE {n}") }))
        .await;
    assert_eq!(status, StatusCode::CONFLICT);

    let (status, updated) = client
        .patch(
            &format!("/api/recipes/{id}"),
            json!({ "information": "Serves 4" }),
        )
        .await;
    assert_eq!(status, StatusCode::OK, "{updated}");
    assert_eq!(updated["information"], "Serves 4");
    assert_eq!(updated["directions"], "Bake");

    let (status, listed) = client.get(&format!("/api/recipes?prefix=quiche_{n}")).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(listed.as_array().unwrap().len(), 1);

    let (status, _) = client.delete(&format!("/api/recipes/{id}")).await;
    assert_eq!(status, StatusCode::NO_CONTENT);
    let (status, _) = client.get(&format!("/api/recipes/{id}")).await;
    assert_eq!(status, StatusCode::NOT_FOUND);

    // Deleting released the name.
    client.recipe(&format!("Quiche {n}")).await;
}

#[tokio::test]
#[ignore = "needs the Firestore emulator"]
async fn ingredients_in_use_cannot_be_deleted() {
    let client = Client::new().await;
    let n = nonce();
    let butter = client
        .ingredient(json!({ "name": format!("Butter {n}") }))
        .await;
    let pie = client.recipe(&format!("Pie {n}")).await;

    let requirement = format!("/api/recipes/{pie}/requirements/{butter}");
    let (status, _) = client
        .put(&requirement, json!({ "quantity": "100g" }))
        .await;
    assert_eq!(status, StatusCode::OK);

    let (_, shown) = client.get(&format!("/api/ingredients/{butter}")).await;
    assert_eq!(shown["used_in"][0]["id"], pie.as_str());

    let (status, conflict) = client.delete(&format!("/api/ingredients/{butter}")).await;
    assert_eq!(status, StatusCode::CONFLICT);
    assert_eq!(conflict["existing"][0]["id"], pie.as_str());

    let (status, _) = client.delete(&requirement).await;
    assert_eq!(status, StatusCode::OK);
    let (status, _) = client.delete(&requirement).await;
    assert_eq!(status, StatusCode::NOT_FOUND);

    let (status, _) = client.delete(&format!("/api/ingredients/{butter}")).await;
    assert_eq!(status, StatusCode::NO_CONTENT);
}

#[tokio::test]
#[ignore = "needs the Firestore emulator"]
async fn requirements_need_existing_records() {
    let client = Client::new().await;
    let n = nonce();
    let pie = client.recipe(&format!("Pie {n}")).await;
    let salt = client
        .ingredient(json!({ "name": format!("Salt {n}") }))
        .await;

    let (status, _) = client
        .put(
            &format!("/api/recipes/{pie}/requirements/missing"),
            json!({ "quantity": "1" }),
        )
        .await;
    assert_eq!(status, StatusCode::NOT_FOUND);

    let (status, _) = client
        .put(
            &format!("/api/recipes/missing/requirements/{salt}"),
            json!({ "quantity": "1" }),
        )
        .await;
    assert_eq!(status, StatusCode::NOT_FOUND);

    // PUT replaces the whole requirement.
    let uri = format!("/api/recipes/{pie}/requirements/{salt}");
    client
        .put(&uri, json!({ "quantity": "1 pinch", "group": "crust" }))
        .await;
    let (_, recipe) = client.put(&uri, json!({ "quantity": "2 pinches" })).await;
    assert_eq!(
        recipe["requirements"][&salt],
        json!({
            "name": format!("Salt {n}"),
            "classification": flags(false, false),
            "quantity": "2 pinches",
            "optional": false,
            "group": "",
        })
    );
}

#[tokio::test]
#[ignore = "needs the Firestore emulator"]
async fn classification_propagates() {
    let client = Client::new().await;
    let n = nonce();
    let butter = client
        .ingredient(json!({ "name": format!("Butter {n}"), "dairy": true }))
        .await;
    let chicken = client
        .ingredient(json!({ "name": format!("Chicken {n}"), "meat": true }))
        .await;
    let crust = client.recipe(&format!("Crust {n}")).await;
    let quiche = client.recipe(&format!("Quiche {n}")).await;
    let lunch = client.recipe(&format!("Lunch {n}")).await;

    client
        .put(
            &format!("/api/recipes/{lunch}/dependencies/{quiche}"),
            json!({}),
        )
        .await;
    client
        .put(
            &format!("/api/recipes/{quiche}/dependencies/{crust}"),
            json!({}),
        )
        .await;
    assert_eq!(client.classification(&lunch).await, flags(false, false));

    // An ingredient added at the bottom reaches every level.
    client
        .put(
            &format!("/api/recipes/{crust}/requirements/{butter}"),
            json!({ "quantity": "100g" }),
        )
        .await;
    for recipe in [&crust, &quiche, &lunch] {
        assert_eq!(client.classification(recipe).await, flags(true, false));
    }

    // So does a change to the ingredient itself.
    client
        .patch(
            &format!("/api/ingredients/{butter}"),
            json!({ "meat": true }),
        )
        .await;
    assert_eq!(client.classification(&lunch).await, flags(true, true));
    client
        .patch(
            &format!("/api/ingredients/{butter}"),
            json!({ "meat": false, "dairy": false }),
        )
        .await;
    assert_eq!(client.classification(&lunch).await, flags(false, false));

    client
        .put(
            &format!("/api/recipes/{quiche}/requirements/{chicken}"),
            json!({ "quantity": "200g" }),
        )
        .await;
    assert_eq!(client.classification(&crust).await, flags(false, false));
    assert_eq!(client.classification(&lunch).await, flags(false, true));

    // Removing a dependency removes what it brought.
    client
        .delete(&format!("/api/recipes/{lunch}/dependencies/{quiche}"))
        .await;
    assert_eq!(client.classification(&lunch).await, flags(false, false));
}

#[tokio::test]
#[ignore = "needs the Firestore emulator"]
async fn dependency_rules() {
    let client = Client::new().await;
    let n = nonce();
    let fajitas = client.recipe(&format!("Fajitas {n}")).await;
    let guacamole = client.recipe(&format!("Guacamole {n}")).await;
    let pico = client.recipe(&format!("Pico {n}")).await;
    let dep = |from: &str, to: &str| format!("/api/recipes/{from}/dependencies/{to}");

    let (status, _) = client.put(&dep(&fajitas, &fajitas), json!({})).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);

    let (status, recipe) = client
        .put(&dep(&fajitas, &guacamole), json!({ "quantity": "1 bowl" }))
        .await;
    assert_eq!(status, StatusCode::OK, "{recipe}");
    assert_eq!(
        recipe["dependencies"][&guacamole],
        json!({ "name": format!("Guacamole {n}"), "quantity": "1 bowl", "optional": false })
    );
    client.put(&dep(&guacamole, &pico), json!({})).await;

    let (status, _) = client.put(&dep(&pico, &fajitas), json!({})).await;
    assert_eq!(status, StatusCode::CONFLICT);

    // A second path to pico is not a cycle.
    let (status, _) = client.put(&dep(&fajitas, &pico), json!({})).await;
    assert_eq!(status, StatusCode::OK);

    let (status, _) = client.put(&dep(&fajitas, "missing"), json!({})).await;
    assert_eq!(status, StatusCode::NOT_FOUND);

    // A recipe lists the recipes using it directly, by name.
    let (_, shown) = client.get(&format!("/api/recipes/{pico}")).await;
    let used_in: Vec<_> = shown["used_in"]
        .as_array()
        .unwrap()
        .iter()
        .map(|r| r["id"].as_str().unwrap())
        .collect();
    assert_eq!(used_in, [fajitas.as_str(), guacamole.as_str()]);

    // Recipes others depend on cannot be deleted.
    let (status, conflict) = client.delete(&format!("/api/recipes/{pico}")).await;
    assert_eq!(status, StatusCode::CONFLICT);
    assert_eq!(conflict["existing"].as_array().unwrap().len(), 2);

    // A rename reaches the copies held by dependants.
    client
        .patch(
            &format!("/api/recipes/{guacamole}"),
            json!({ "name": format!("Guac {n}") }),
        )
        .await;
    let (_, shown) = client.get(&format!("/api/recipes/{fajitas}")).await;
    assert_eq!(
        shown["dependencies"][&guacamole]["name"],
        format!("Guac {n}")
    );
}

#[tokio::test]
#[ignore = "needs the Firestore emulator"]
async fn ingredient_rename_reaches_recipes() {
    let client = Client::new().await;
    let n = nonce();
    let onion = client
        .ingredient(json!({ "name": format!("Onion {n}") }))
        .await;
    let soup = client.recipe(&format!("Soup {n}")).await;
    client
        .put(
            &format!("/api/recipes/{soup}/requirements/{onion}"),
            json!({ "quantity": "2" }),
        )
        .await;

    client
        .patch(
            &format!("/api/ingredients/{onion}"),
            json!({ "name": format!("Red onion {n}") }),
        )
        .await;
    let (_, recipe) = client.get(&format!("/api/recipes/{soup}")).await;
    assert_eq!(
        recipe["requirements"][&onion]["name"],
        format!("Red onion {n}")
    );
}

#[tokio::test]
#[ignore = "needs the Firestore emulator"]
async fn tags_and_labels() {
    let client = Client::new().await;
    let n = nonce();
    let label = format!("Spicy{n}");
    let simple = format!("spicy{n}");
    let chili = client.recipe(&format!("Chili {n}")).await;
    let salsa = client.recipe(&format!("Salsa {n}")).await;
    let tag = |recipe: &str, label: &str| format!("/api/recipes/{recipe}/tags/{label}");

    let (status, recipe) = client.put(&tag(&chili, &label), json!(null)).await;
    assert_eq!(status, StatusCode::OK, "{recipe}");
    assert_eq!(recipe["tags"], json!([simple]));
    // Tagging twice changes nothing.
    client.put(&tag(&chili, &label), json!(null)).await;
    client.put(&tag(&salsa, &simple), json!(null)).await;

    let (status, shown) = client.get(&format!("/api/labels/{simple}")).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(shown["name"], label);
    assert_eq!(shown["recipe_count"], 2);
    assert_eq!(shown["recipes"].as_array().unwrap().len(), 2);

    let (status, _) = client.put(&tag(&chili, "two%20words"), json!(null)).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);

    // Renaming a label retags its recipes.
    let (status, renamed) = client
        .patch(
            &format!("/api/labels/{simple}"),
            json!({ "name": format!("Hot{n}") }),
        )
        .await;
    assert_eq!(status, StatusCode::OK, "{renamed}");
    let (status, _) = client.get(&format!("/api/labels/{simple}")).await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    let (_, recipe) = client.get(&format!("/api/recipes/{chili}")).await;
    assert_eq!(recipe["tags"], json!([format!("hot{n}")]));

    // Untagging and deleting recipes lower the count; the label goes at 0.
    let hot = format!("hot{n}");
    client.delete(&tag(&chili, &hot)).await;
    let (_, shown) = client.get(&format!("/api/labels/{hot}")).await;
    assert_eq!(shown["recipe_count"], 1);
    let (status, _) = client.delete(&tag(&chili, &hot)).await;
    assert_eq!(status, StatusCode::NOT_FOUND);

    client.delete(&format!("/api/recipes/{salsa}")).await;
    let (status, _) = client.get(&format!("/api/labels/{hot}")).await;
    assert_eq!(status, StatusCode::NOT_FOUND);
}

#[tokio::test]
#[ignore = "needs the Firestore emulator"]
async fn deleting_a_label_untags_recipes() {
    let client = Client::new().await;
    let n = nonce();
    let label = format!("drink{n}");
    let horchata = client.recipe(&format!("Horchata {n}")).await;
    client
        .put(
            &format!("/api/recipes/{horchata}/tags/{label}"),
            json!(null),
        )
        .await;

    let (status, listed) = client.get(&format!("/api/labels?prefix={label}")).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(listed.as_array().unwrap().len(), 1);

    let (status, _) = client.delete(&format!("/api/labels/{label}")).await;
    assert_eq!(status, StatusCode::NO_CONTENT);
    let (_, recipe) = client.get(&format!("/api/recipes/{horchata}")).await;
    assert_eq!(recipe["tags"], json!([]));
}

/// Two servers on the same database, as Cloud Run runs with more than one
/// instance: each sees the other's writes despite its cache.
#[tokio::test]
#[ignore = "needs the Firestore emulator"]
async fn instances_see_each_others_writes() {
    let (a, b) = (Client::new().await, Client::new().await);
    let n = nonce();
    let search = format!("/api/recipes?prefix=gazpacho%20{n}");

    let (status, listed) = b.get(&search).await;
    assert_eq!(status, StatusCode::OK);
    assert_eq!(listed, json!([]));

    let id = a.recipe(&format!("Gazpacho {n}")).await;
    let (_, listed) = b.get(&search).await;
    assert_eq!(listed[0]["id"], id);

    let (status, _) = b
        .patch(&format!("/api/recipes/{id}"), json!({ "author": "Abuela" }))
        .await;
    assert_eq!(status, StatusCode::OK);
    let (_, shown) = a.get(&format!("/api/recipes/{id}")).await;
    assert_eq!(shown["author"], "Abuela");

    let (status, _) = a.delete(&format!("/api/recipes/{id}")).await;
    assert_eq!(status, StatusCode::NO_CONTENT);
    let (status, _) = b.get(&format!("/api/recipes/{id}")).await;
    assert_eq!(status, StatusCode::NOT_FOUND);
    let (_, listed) = b.get(&search).await;
    assert_eq!(listed, json!([]));
}
