//! HTTP API for knife, a shared family recipe book.

pub mod auth;
mod error;
pub mod members;
mod routes;
pub mod store;

use auth::{CurrentUser, TokenError, Verifier};
use axum::extract::{Request, State};
use axum::http::{Method, header};
use axum::middleware::{self, Next};
use axum::response::Response;
use axum::routing::get;
use axum::{Extension, Json, Router};
pub use error::ApiError;
use members::Members;
use serde_json::{Value, json};
use std::sync::Arc;
use store::Store;

/// Who may use the API.
pub struct Auth {
    pub verifier: Verifier,
    pub members: Members,
}

pub fn app(auth: Auth, store: Store) -> Router {
    let api = routes::router(Arc::new(store)).route("/me", get(me));

    let api = Router::new()
        .route("/health", get(|| async { "ok" }))
        .merge(members_only(api, Arc::new(auth)));

    Router::new().nest("/api", api)
}

fn members_only(router: Router, auth: Arc<Auth>) -> Router {
    router.route_layer(middleware::from_fn_with_state(auth, require_member))
}

/// Reject requests without a valid ID token from a family member, and changes
/// from members who are not editors. Makes the [`CurrentUser`] and their
/// [`members::Member`] record available to handlers.
async fn require_member(
    State(state): State<Arc<Auth>>,
    mut request: Request,
    next: Next,
) -> Result<Response, ApiError> {
    let token = request
        .headers()
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or_else(|| ApiError::unauthorized("missing bearer token"))?;

    let user = state.verifier.verify(token).await.map_err(|e| match e {
        TokenError::KeyFetch(_) => ApiError::internal(e),
        _ => ApiError::unauthorized(e.to_string()),
    })?;

    let member = state
        .members
        .get(&user.uid)
        .await
        .map_err(ApiError::internal)?
        .ok_or_else(|| ApiError::forbidden("not a member of this recipe book"))?;

    // Every route that changes the recipe book uses a non-safe method.
    let reads = matches!(*request.method(), Method::GET | Method::HEAD);
    if !reads && !member.editor {
        return Err(ApiError::forbidden(
            "this account can only read the recipe book",
        ));
    }

    request.extensions_mut().insert(user);
    request.extensions_mut().insert(member);
    Ok(next.run(request).await)
}

async fn me(
    Extension(user): Extension<CurrentUser>,
    Extension(member): Extension<members::Member>,
) -> Json<Value> {
    Json(json!({ "uid": user.uid, "email": user.email, "editor": member.editor }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::auth::tests::{claims, sign, test_verifier};
    use axum::body::{Body, to_bytes};
    use axum::http::{Request, StatusCode};
    use knife_core::UserId;
    use members::Member;
    use std::collections::HashMap;
    use tower::ServiceExt;

    /// The auth layer around `/api/me`, without storage.
    fn test_app() -> Router {
        let auth = Auth {
            verifier: test_verifier(),
            members: Members::Fixed(HashMap::from([
                (UserId::from("alice"), member(true)),
                (UserId::from("bob"), member(false)),
            ])),
        };
        let api = Router::new()
            .route("/health", get(|| async { "ok" }))
            .merge(members_only(
                Router::new().route("/me", get(me).post(|| async { "{}" })),
                Arc::new(auth),
            ));
        Router::new().nest("/api", api)
    }

    fn member(editor: bool) -> Member {
        Member {
            display_name: "Test".into(),
            editor,
        }
    }

    async fn get_me(token: Option<&str>) -> (StatusCode, Value) {
        send(Request::get("/api/me"), token).await
    }

    async fn send(
        mut request: axum::http::request::Builder,
        token: Option<&str>,
    ) -> (StatusCode, Value) {
        if let Some(token) = token {
            request = request.header("Authorization", format!("Bearer {token}"));
        }
        let response = test_app()
            .oneshot(request.body(Body::empty()).unwrap())
            .await
            .unwrap();

        let status = response.status();
        let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
        (status, serde_json::from_slice(&body).unwrap())
    }

    #[tokio::test]
    async fn health_is_public() {
        let response = test_app()
            .oneshot(Request::get("/api/health").body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(response.status(), StatusCode::OK);
    }

    #[tokio::test]
    async fn missing_token_is_401() {
        let (status, body) = get_me(None).await;
        assert_eq!(status, StatusCode::UNAUTHORIZED);
        assert_eq!(body["status"], 401);
    }

    #[tokio::test]
    async fn invalid_token_is_401() {
        let (status, _) = get_me(Some("not-a-token")).await;
        assert_eq!(status, StatusCode::UNAUTHORIZED);
    }

    #[tokio::test]
    async fn non_member_is_403() {
        let (status, _) = get_me(Some(&sign(&claims("mallory"), "test-key"))).await;
        assert_eq!(status, StatusCode::FORBIDDEN);
    }

    #[tokio::test]
    async fn member_gets_through() {
        let (status, body) = get_me(Some(&sign(&claims("alice"), "test-key"))).await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["uid"], "alice");
        assert_eq!(body["email"], "alice@example.com");
        assert_eq!(body["editor"], true);
    }

    #[tokio::test]
    async fn members_are_read_only_by_default() {
        let bob = sign(&claims("bob"), "test-key");
        let (status, body) = get_me(Some(&bob)).await;
        assert_eq!(status, StatusCode::OK);
        assert_eq!(body["editor"], false);

        let (status, _) = send(Request::post("/api/me"), Some(&bob)).await;
        assert_eq!(status, StatusCode::FORBIDDEN);
    }

    #[tokio::test]
    async fn editors_can_write() {
        let alice = sign(&claims("alice"), "test-key");
        let (status, _) = send(Request::post("/api/me"), Some(&alice)).await;
        assert_eq!(status, StatusCode::OK);
    }

    #[test]
    fn editor_defaults_to_false() {
        let member: Member = serde_json::from_value(json!({ "display_name": "Bob" })).unwrap();
        assert!(!member.editor);
    }
}
