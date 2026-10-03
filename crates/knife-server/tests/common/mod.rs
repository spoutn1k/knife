//! Test client for the API, against the Firestore emulator.
//!
//! The emulator keeps data between tests, so tests use names with a unique
//! suffix from [`nonce`] and never assume a collection is empty.

#![allow(dead_code)]

use axum::Router;
use axum::body::{Body, to_bytes};
use axum::http::{Method, Request, StatusCode};
use base64::Engine;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use firestore::FirestoreDb;
use knife_core::UserId;
use knife_server::auth::Verifier;
use knife_server::members::Members;
use knife_server::store::Store;
use knife_server::{Auth, app};
use serde_json::{Value, json};
use std::collections::HashSet;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};
use tower::ServiceExt;

pub const PROJECT: &str = "knife-c51d5";
pub const UID: &str = "tester";

pub struct Client {
    pub app: Router,
    pub token: String,
}

/// A unique suffix for names created by one test.
pub fn nonce() -> String {
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_micros();
    format!("{now}x{}", COUNTER.fetch_add(1, Ordering::Relaxed))
}

/// An Auth emulator style token: unsigned, with the claims Firebase sets.
fn emulator_token(uid: &str) -> String {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    let claims = json!({
        "sub": uid,
        "aud": PROJECT,
        "iss": format!("https://securetoken.google.com/{PROJECT}"),
        "iat": now,
        "exp": now + 3600,
        "auth_time": now,
    });
    format!(
        "{}.{}.",
        URL_SAFE_NO_PAD.encode(r#"{"alg":"none","typ":"JWT"}"#),
        URL_SAFE_NO_PAD.encode(claims.to_string())
    )
}

impl Client {
    pub async fn new() -> Self {
        // Show the causes of 500s, which are only logged.
        let _ = tracing_subscriber::fmt().with_test_writer().try_init();
        assert!(
            std::env::var_os("FIRESTORE_EMULATOR_HOST").is_some(),
            "FIRESTORE_EMULATOR_HOST is not set; run under `firebase emulators:exec`"
        );
        let db = FirestoreDb::new(PROJECT).await.unwrap();
        let auth = Auth {
            verifier: Verifier::emulator(PROJECT),
            members: Members::Fixed(HashSet::from([UserId::from(UID)])),
        };
        Self {
            app: app(auth, Store::new(db)),
            token: emulator_token(UID),
        }
    }

    pub async fn send(
        &self,
        method: Method,
        uri: &str,
        body: Option<Value>,
    ) -> (StatusCode, Value) {
        let request = Request::builder()
            .method(method)
            .uri(uri)
            .header("Authorization", format!("Bearer {}", self.token));
        let request = match body {
            Some(body) => request
                .header("Content-Type", "application/json")
                .body(Body::from(body.to_string())),
            None => request.body(Body::empty()),
        };

        let response = self.app.clone().oneshot(request.unwrap()).await.unwrap();
        let status = response.status();
        let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
        let body = serde_json::from_slice(&bytes)
            .unwrap_or_else(|_| Value::String(String::from_utf8_lossy(&bytes).into()));
        (status, body)
    }

    pub async fn get(&self, uri: &str) -> (StatusCode, Value) {
        self.send(Method::GET, uri, None).await
    }

    pub async fn post(&self, uri: &str, body: Value) -> (StatusCode, Value) {
        self.send(Method::POST, uri, Some(body)).await
    }

    pub async fn put(&self, uri: &str, body: Value) -> (StatusCode, Value) {
        self.send(Method::PUT, uri, Some(body)).await
    }

    pub async fn patch(&self, uri: &str, body: Value) -> (StatusCode, Value) {
        self.send(Method::PATCH, uri, Some(body)).await
    }

    pub async fn delete(&self, uri: &str) -> (StatusCode, Value) {
        self.send(Method::DELETE, uri, None).await
    }

    /// Create an ingredient and return its id.
    pub async fn ingredient(&self, body: Value) -> String {
        let (status, created) = self.post("/api/ingredients", body).await;
        assert_eq!(status, StatusCode::CREATED, "{created}");
        created["id"].as_str().unwrap().to_owned()
    }

    /// Create a recipe and return its id.
    pub async fn recipe(&self, name: &str) -> String {
        let (status, created) = self.post("/api/recipes", json!({ "name": name })).await;
        assert_eq!(status, StatusCode::CREATED, "{created}");
        created["id"].as_str().unwrap().to_owned()
    }

    pub async fn classification(&self, recipe: &str) -> Value {
        let (status, body) = self.get(&format!("/api/recipes/{recipe}")).await;
        assert_eq!(status, StatusCode::OK, "{body}");
        body["classification"].clone()
    }
}

/// Assert a response's status, showing its body on failure, and return the
/// body.
pub fn expect((status, body): (StatusCode, Value), expected: StatusCode) -> Value {
    assert_eq!(status, expected, "{body}");
    body
}
