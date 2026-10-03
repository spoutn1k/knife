//! Firebase Auth sign-in and authenticated calls to the knife API.

use crate::Error;
use crate::credentials::Credentials;
use reqwest::blocking::Client as Http;
use reqwest::{Method, Url};
use serde::Serialize;
use serde_json::{Value, json};

/// Base URL of a Google identity API, or of the Auth emulator when
/// `FIREBASE_AUTH_EMULATOR_HOST` is set, as the Firebase SDKs do.
fn identity_url(api: &str) -> String {
    match std::env::var("FIREBASE_AUTH_EMULATOR_HOST") {
        Ok(host) => format!("http://{host}/{api}"),
        Err(_) => format!("https://{api}"),
    }
}

/// Exchange an email and password for a refresh token.
pub fn sign_in(api_key: &str, email: &str, password: &str) -> Result<String, Error> {
    let url = format!(
        "{}/v1/accounts:signInWithPassword?key={api_key}",
        identity_url("identitytoolkit.googleapis.com")
    );
    let body = identity_call(
        Http::new()
            .post(url)
            .json(&json!({ "email": email, "password": password, "returnSecureToken": true })),
    )?;
    Ok(body["refreshToken"].as_str().unwrap_or_default().into())
}

/// Exchange a refresh token for a fresh ID token, valid for an hour.
fn id_token(http: &Http, credentials: &Credentials) -> Result<String, Error> {
    let url = format!(
        "{}/v1/token?key={}",
        identity_url("securetoken.googleapis.com"),
        credentials.api_key
    );
    let body = identity_call(http.post(url).form(&[
        ("grant_type", "refresh_token"),
        ("refresh_token", credentials.refresh_token.as_str()),
    ]))?;
    Ok(body["id_token"].as_str().unwrap_or_default().into())
}

fn identity_call(request: reqwest::blocking::RequestBuilder) -> Result<Value, Error> {
    let response = request.send()?;
    let status = response.status();
    let body: Value = response.json()?;
    if status.is_success() {
        Ok(body)
    } else {
        let message = body["error"]["message"].as_str().unwrap_or("unknown error");
        Err(Error::SignIn(message.into()))
    }
}

pub struct Client {
    http: Http,
    url: Url,
    token: String,
}

impl Client {
    pub fn new(credentials: &Credentials) -> Result<Self, Error> {
        let http = Http::new();
        let token = id_token(&http, credentials)?;
        let url = Url::parse(&credentials.url).map_err(|_| Error::Url(credentials.url.clone()))?;
        Ok(Self { http, url, token })
    }

    /// Call `/api/<segments...>`. Each segment is percent-encoded, so ids
    /// and label names can hold any character.
    pub fn call(
        &self,
        method: Method,
        segments: &[&str],
        query: &[(&str, &str)],
        body: Option<&impl Serialize>,
    ) -> Result<Value, Error> {
        let mut url = self.url.clone();
        url.path_segments_mut()
            .map_err(|()| Error::Url(self.url.to_string()))?
            .pop_if_empty()
            .push("api")
            .extend(segments);

        let mut request = self
            .http
            .request(method.clone(), url)
            .bearer_auth(&self.token)
            .query(query);
        if let Some(body) = body {
            request = request.json(body);
        }

        let response = request.send()?;
        let status = response.status();
        let text = response.text()?;
        if status.is_success() {
            // 204 No Content has no body.
            return Ok(serde_json::from_str(&text).unwrap_or(Value::Null));
        }

        // Errors are RFC 9457 problem bodies; fall back to the raw text.
        let problem: Value = serde_json::from_str(&text).unwrap_or(Value::Null);
        Err(Error::Api {
            method,
            path: format!("/api/{}", segments.join("/")),
            status: status.as_u16(),
            detail: problem["detail"].as_str().map_or(text, String::from),
            existing: problem.get("existing").cloned(),
        })
    }

    pub fn get(&self, segments: &[&str], query: &[(&str, &str)]) -> Result<Value, Error> {
        self.call(Method::GET, segments, query, None::<&()>)
    }

    pub fn post<T: Serialize>(&self, segments: &[&str], body: &T) -> Result<Value, Error> {
        self.call(Method::POST, segments, &[], Some(body))
    }

    pub fn put<T: Serialize>(&self, segments: &[&str], body: &T) -> Result<Value, Error> {
        self.call(Method::PUT, segments, &[], Some(body))
    }

    pub fn patch<T: Serialize>(&self, segments: &[&str], body: &T) -> Result<Value, Error> {
        self.call(Method::PATCH, segments, &[], Some(body))
    }

    pub fn delete(&self, segments: &[&str]) -> Result<Value, Error> {
        self.call(Method::DELETE, segments, &[], None::<&()>)
    }
}
