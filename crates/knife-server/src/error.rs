use crate::store::StoreError;
use axum::extract::rejection::{JsonRejection, PathRejection, QueryRejection};
use axum::http::{StatusCode, header};
use axum::response::{IntoResponse, Response};
use serde::Serialize;
use serde_json::Value;

/// An error response, sent as an RFC 9457 problem details body.
#[derive(Debug)]
pub struct ApiError {
    pub status: StatusCode,
    pub detail: String,
    /// On a 409, the record causing the conflict.
    pub existing: Option<Value>,
}

impl ApiError {
    pub fn new(status: StatusCode, detail: impl Into<String>) -> Self {
        Self {
            status,
            detail: detail.into(),
            existing: None,
        }
    }

    pub fn unauthorized(detail: impl Into<String>) -> Self {
        Self::new(StatusCode::UNAUTHORIZED, detail)
    }

    pub fn forbidden(detail: impl Into<String>) -> Self {
        Self::new(StatusCode::FORBIDDEN, detail)
    }

    /// Log the cause and hide it from the client.
    pub fn internal(cause: impl std::fmt::Display) -> Self {
        tracing::error!("{cause}");
        Self::new(StatusCode::INTERNAL_SERVER_ERROR, "internal error")
    }
}

impl From<StoreError> for ApiError {
    fn from(err: StoreError) -> Self {
        use knife_core::Error as Rule;

        match err {
            StoreError::NotFound(_) => Self::new(StatusCode::NOT_FOUND, err.to_string()),
            StoreError::Conflict { detail, existing } => Self {
                status: StatusCode::CONFLICT,
                detail,
                existing,
            },
            StoreError::Rule(Rule::DependencyCycle) => {
                Self::new(StatusCode::CONFLICT, err.to_string())
            }
            StoreError::Rule(Rule::MissingRecipe(_))
            | StoreError::Firestore(_)
            | StoreError::Cache(_) => Self::internal(err),
            StoreError::Rule(_) => Self::new(StatusCode::BAD_REQUEST, err.to_string()),
        }
    }
}

impl From<JsonRejection> for ApiError {
    fn from(rejection: JsonRejection) -> Self {
        Self::new(rejection.status(), rejection.body_text())
    }
}

impl From<QueryRejection> for ApiError {
    fn from(rejection: QueryRejection) -> Self {
        Self::new(rejection.status(), rejection.body_text())
    }
}

impl From<PathRejection> for ApiError {
    fn from(rejection: PathRejection) -> Self {
        Self::new(rejection.status(), rejection.body_text())
    }
}

#[derive(Serialize)]
struct Problem<'a> {
    title: &'a str,
    status: u16,
    detail: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    existing: Option<&'a Value>,
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let body = Problem {
            title: self.status.canonical_reason().unwrap_or("Error"),
            status: self.status.as_u16(),
            detail: &self.detail,
            existing: self.existing.as_ref(),
        };
        let body = serde_json::to_vec(&body).expect("problem serializes");

        (
            self.status,
            [(header::CONTENT_TYPE, "application/problem+json")],
            body,
        )
            .into_response()
    }
}
