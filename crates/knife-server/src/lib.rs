//! HTTP API for knife, a shared family recipe book.

pub mod auth;
mod error;
pub mod members;
mod routes;
pub mod store;

use auth::{CurrentUser, TokenError, Verifier};
use axum::extract::{Request, State};
use axum::http::header;
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

/// Reject requests without a valid ID token from a family member, and make
/// the [`CurrentUser`] available to handlers.
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

    if !state
        .members
        .contains(&user.uid)
        .await
        .map_err(ApiError::internal)?
    {
        return Err(ApiError::forbidden("not a member of this recipe book"));
    }

    request.extensions_mut().insert(user);
    Ok(next.run(request).await)
}

async fn me(Extension(user): Extension<CurrentUser>) -> Json<Value> {
    Json(json!({ "uid": user.uid, "email": user.email }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::auth::tests::{claims, sign, test_verifier};
    use axum::body::{Body, to_bytes};
    use axum::http::{Request, StatusCode};
    use knife_core::UserId;
    use std::collections::HashSet;
    use tower::ServiceExt;

    /// The auth layer around `/api/me`, without storage.
    fn test_app() -> Router {
        let auth = Auth {
            verifier: test_verifier(),
            members: Members::Fixed(HashSet::from([UserId::from("alice")])),
        };
        let api = Router::new()
            .route("/health", get(|| async { "ok" }))
            .merge(members_only(
                Router::new().route("/me", get(me)),
                Arc::new(auth),
            ));
        Router::new().nest("/api", api)
    }

    async fn get_me(token: Option<&str>) -> (StatusCode, Value) {
        let mut request = Request::get("/api/me");
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
    }
}
