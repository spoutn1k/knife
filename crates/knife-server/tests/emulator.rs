//! End-to-end auth against the Firebase emulators. Run from the repo root,
//! with every other emulator test:
//!
//! ```sh
//! firebase emulators:exec --only auth,firestore "cargo emulator-test"
//! ```

use axum::body::Body;
use axum::http::{Request, StatusCode};
use firestore::FirestoreDb;
use knife_server::auth::Verifier;
use knife_server::members::{self, Member, Members};
use knife_server::store::Store;
use knife_server::{Auth, app};
use serde_json::{Value, json};
use std::time::{SystemTime, UNIX_EPOCH};
use tower::ServiceExt;

const PROJECT: &str = "knife-c51d5";

fn emulator_host(var: &str) -> String {
    std::env::var(var)
        .unwrap_or_else(|_| panic!("{var} is not set; run under `firebase emulators:exec`"))
}

/// Create an account in the Auth emulator and return its uid and ID token.
async fn sign_up() -> (String, String) {
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let url = format!(
        "http://{}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=fake-api-key",
        emulator_host("FIREBASE_AUTH_EMULATOR_HOST")
    );

    let response: Value = reqwest::Client::new()
        .post(url)
        .json(&json!({
            "email": format!("user{nonce}@example.com"),
            "password": "correct horse battery staple",
            "returnSecureToken": true,
        }))
        .send()
        .await
        .unwrap()
        .error_for_status()
        .unwrap()
        .json()
        .await
        .unwrap();

    (
        response["localId"].as_str().unwrap().to_owned(),
        response["idToken"].as_str().unwrap().to_owned(),
    )
}

async fn get_me(app: axum::Router, token: &str) -> StatusCode {
    app.oneshot(
        Request::get("/api/me")
            .header("Authorization", format!("Bearer {token}"))
            .body(Body::empty())
            .unwrap(),
    )
    .await
    .unwrap()
    .status()
}

#[tokio::test]
#[ignore = "needs the Firebase emulators"]
async fn only_members_get_in() {
    emulator_host("FIRESTORE_EMULATOR_HOST");
    let db = FirestoreDb::new(PROJECT).await.unwrap();
    let app = app(
        Auth {
            verifier: Verifier::emulator(PROJECT),
            members: Members::firestore(db.clone()),
        },
        Store::new(db.clone()),
    );

    let (uid, token) = sign_up().await;
    assert_eq!(get_me(app.clone(), &token).await, StatusCode::FORBIDDEN);

    let _: Member = db
        .fluent()
        .insert()
        .into(members::COLLECTION)
        .document_id(&uid)
        .object(&Member {
            display_name: "Test".into(),
        })
        .execute()
        .await
        .unwrap();
    assert_eq!(get_me(app, &token).await, StatusCode::OK);
}
