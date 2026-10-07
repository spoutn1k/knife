//! End-to-end auth against the Firebase emulators. Run from the repo root,
//! with every other emulator test:
//!
//! ```sh
//! firebase emulators:exec --only auth,firestore "cargo emulator-test"
//! ```

use axum::body::Body;
use axum::body::to_bytes;
use axum::http::{Method, Request, StatusCode};
use firestore::FirestoreDb;
use knife_server::accounts::Accounts;
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

/// Sign in to an existing account and return its ID token.
async fn sign_in(email: &str, password: &str) -> Result<String, Value> {
    let url = format!(
        "http://{}/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=fake-api-key",
        emulator_host("FIREBASE_AUTH_EMULATOR_HOST")
    );
    let response: Value = reqwest::Client::new()
        .post(url)
        .json(&json!({ "email": email, "password": password, "returnSecureToken": true }))
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    match response["idToken"].as_str() {
        Some(token) => Ok(token.to_owned()),
        None => Err(response),
    }
}

/// The app against both emulators, with members in Firestore.
async fn emulated_app() -> (axum::Router, FirestoreDb) {
    let db = FirestoreDb::new(PROJECT).await.unwrap();
    let app = app(
        Auth {
            verifier: Verifier::emulator(PROJECT),
            members: Members::firestore(db.clone()),
            accounts: Accounts::emulator(PROJECT, &emulator_host("FIREBASE_AUTH_EMULATOR_HOST")),
        },
        Store::new(db.clone()),
    );
    (app, db)
}

async fn add_member(db: &FirestoreDb, uid: &str, member: Member) {
    let _: Member = db
        .fluent()
        .insert()
        .into(members::COLLECTION)
        .document_id(uid)
        .object(&member)
        .execute()
        .await
        .unwrap();
}

async fn send(
    app: &axum::Router,
    token: &str,
    method: Method,
    uri: &str,
    body: Option<Value>,
) -> (StatusCode, Value) {
    let request = Request::builder()
        .method(method)
        .uri(uri)
        .header("Authorization", format!("Bearer {token}"))
        .header("Content-Type", "application/json");
    let body = body.map_or(Body::empty(), |b| Body::from(b.to_string()));
    let response = app
        .clone()
        .oneshot(request.body(body).unwrap())
        .await
        .unwrap();

    let status = response.status();
    let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    (
        status,
        serde_json::from_slice(&bytes).unwrap_or(Value::Null),
    )
}

async fn get_me(app: axum::Router, token: &str) -> StatusCode {
    send(&app, token, Method::GET, "/api/me", None).await.0
}

#[tokio::test]
#[ignore = "needs the Firebase emulators"]
async fn only_members_get_in() {
    emulator_host("FIRESTORE_EMULATOR_HOST");
    let (app, db) = emulated_app().await;

    let (uid, token) = sign_up().await;
    assert_eq!(get_me(app.clone(), &token).await, StatusCode::FORBIDDEN);

    let member = Member {
        display_name: "Test".into(),
        editor: false,
        admin: false,
    };
    add_member(&db, &uid, member).await;
    assert_eq!(get_me(app, &token).await, StatusCode::OK);
}

#[tokio::test]
#[ignore = "needs the Firebase emulators"]
async fn admins_manage_members() {
    let (app, db) = emulated_app().await;
    let (admin_uid, admin) = sign_up().await;
    let admin_member = Member {
        display_name: "Admin".into(),
        editor: true,
        admin: true,
    };
    add_member(&db, &admin_uid, admin_member).await;

    // A new account, created as a reader.
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let email = format!("new{nonce}@example.com");
    let (status, created) = send(
        &app,
        &admin,
        Method::POST,
        "/api/members",
        Some(json!({ "email": email, "display_name": "New", "password": "secret1" })),
    )
    .await;
    assert_eq!(status, StatusCode::CREATED, "{created}");
    assert_eq!(created["email"], email.as_str());
    assert_eq!(created["editor"], false);
    let uid = created["uid"].as_str().unwrap().to_owned();
    let member_uri = format!("/api/members/{uid}");

    let (status, listed) = send(&app, &admin, Method::GET, "/api/members", None).await;
    assert_eq!(status, StatusCode::OK, "{listed}");
    assert!(listed.as_array().unwrap().contains(&created));

    // They can sign in and read, not write, nor manage members.
    let token = sign_in(&email, "secret1").await.unwrap();
    let (_, me) = send(&app, &token, Method::GET, "/api/me", None).await;
    assert_eq!(me["editor"], false);
    let (status, _) = send(&app, &token, Method::GET, "/api/members", None).await;
    assert_eq!(status, StatusCode::FORBIDDEN);

    // Adding them again is a conflict, with or without a password.
    for password in [None, Some("secret1")] {
        let body = json!({ "email": email, "display_name": "New", "password": password });
        let (status, _) = send(&app, &admin, Method::POST, "/api/members", Some(body)).await;
        assert_eq!(status, StatusCode::CONFLICT);
    }

    // Made an editor, with a new password.
    let body = json!({ "editor": true, "password": "secret2" });
    let (status, updated) = send(&app, &admin, Method::PATCH, &member_uri, Some(body)).await;
    assert_eq!(status, StatusCode::OK, "{updated}");
    assert_eq!(updated["editor"], true);
    assert!(sign_in(&email, "secret1").await.is_err());
    let token = sign_in(&email, "secret2").await.unwrap();
    let (_, me) = send(&app, &token, Method::GET, "/api/me", None).await;
    assert_eq!(me["editor"], true);

    // Admins cannot lock themselves out.
    let own_uri = format!("/api/members/{admin_uid}");
    let body = json!({ "admin": false });
    let (status, _) = send(&app, &admin, Method::PATCH, &own_uri, Some(body)).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
    let (status, _) = send(&app, &admin, Method::DELETE, &own_uri, None).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);

    // Removed: neither a member nor an account any more.
    let (status, _) = send(&app, &admin, Method::DELETE, &member_uri, None).await;
    assert_eq!(status, StatusCode::NO_CONTENT);
    assert_eq!(get_me(app.clone(), &token).await, StatusCode::FORBIDDEN);
    assert!(sign_in(&email, "secret2").await.is_err());
    let (status, _) = send(&app, &admin, Method::DELETE, &member_uri, None).await;
    assert_eq!(status, StatusCode::NOT_FOUND);
}

#[tokio::test]
#[ignore = "needs the Firebase emulators"]
async fn existing_accounts_join_without_a_password() {
    let (app, db) = emulated_app().await;
    let (admin_uid, admin) = sign_up().await;
    let admin_member = Member {
        display_name: "Admin".into(),
        editor: false,
        admin: true,
    };
    add_member(&db, &admin_uid, admin_member).await;

    let (uid, token) = sign_up().await;
    let (_, me) = send(&app, &admin, Method::GET, "/api/me", None).await;
    assert_eq!(me["admin"], true);
    let (_, listed) = send(&app, &admin, Method::GET, "/api/members", None).await;
    let email = listed
        .as_array()
        .unwrap()
        .iter()
        .find(|m| m["uid"] == admin_uid.as_str())
        .map(|m| m["email"].clone())
        .unwrap();
    assert!(email.as_str().unwrap().ends_with("@example.com"));

    // The second account's email, from the emulator.
    let url = format!(
        "http://{}/identitytoolkit.googleapis.com/v1/projects/{PROJECT}/accounts:lookup",
        emulator_host("FIREBASE_AUTH_EMULATOR_HOST")
    );
    let found: Value = reqwest::Client::new()
        .post(url)
        .bearer_auth("owner")
        .json(&json!({ "localId": [uid] }))
        .send()
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    let email = found["users"][0]["email"].as_str().unwrap();

    let body = json!({ "email": email, "display_name": "Joined" });
    let (status, created) = send(&app, &admin, Method::POST, "/api/members", Some(body)).await;
    assert_eq!(status, StatusCode::CREATED, "{created}");
    assert_eq!(created["uid"], uid.as_str());
    assert_eq!(get_me(app.clone(), &token).await, StatusCode::OK);

    // An unknown email needs a password.
    let body = json!({ "email": format!("nobody-{uid}@example.com"), "display_name": "Nobody" });
    let (status, _) = send(&app, &admin, Method::POST, "/api/members", Some(body)).await;
    assert_eq!(status, StatusCode::BAD_REQUEST);
}
