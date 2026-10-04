//! Firebase Auth over its REST API, as chopstick does: email and password
//! sign-in, then refresh-token exchanges for short-lived ID tokens.
//!
//! The refresh token is kept in `localStorage`, so a reload keeps the user
//! signed in.

use crate::Error;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

/// Set at build time to sign in against the Auth emulator, as the Firebase
/// SDKs do: `FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 dx serve`.
const EMULATOR_HOST: Option<&str> = option_env!("FIREBASE_AUTH_EMULATOR_HOST");

/// Set at build time to override the web API key that Firebase Hosting
/// serves at `/__/firebase/init.json`.
const API_KEY: Option<&str> = option_env!("KNIFE_API_KEY");

const STORAGE_KEY: &str = "spoon.session";

/// ID tokens are refreshed this long before they expire, in milliseconds.
const EXPIRY_MARGIN_MS: f64 = 60_000.0;

/// Where to sign in, with which project key.
#[derive(Debug, Clone, PartialEq)]
pub struct Identity {
    api_key: String,
}

impl Identity {
    /// The project's web API key: built in, or read from Firebase Hosting's
    /// reserved URL. The emulator accepts any key.
    pub async fn load(http: &reqwest::Client, origin: &str) -> Result<Self, Error> {
        if let Some(key) = API_KEY {
            return Ok(Self {
                api_key: key.into(),
            });
        }
        if EMULATOR_HOST.is_some() {
            return Ok(Self {
                api_key: "emulator".into(),
            });
        }

        #[derive(Deserialize)]
        #[serde(rename_all = "camelCase")]
        struct InitJson {
            api_key: String,
        }
        let init: InitJson = http
            .get(format!("{origin}/__/firebase/init.json"))
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;
        Ok(Self {
            api_key: init.api_key,
        })
    }

    /// Exchange an email and password for a session and a first ID token.
    pub async fn sign_in(
        &self,
        http: &reqwest::Client,
        email: &str,
        password: &str,
    ) -> Result<(Session, IdToken), Error> {
        let url = format!(
            "{}/v1/accounts:signInWithPassword?key={}",
            identity_url("identitytoolkit.googleapis.com"),
            self.api_key
        );
        let body = identity_call(
            http.post(url)
                .json(&json!({ "email": email, "password": password, "returnSecureToken": true })),
            Error::SignIn,
        )
        .await?;

        let field = |name: &str| body[name].as_str().unwrap_or_default().to_owned();
        let session = Session {
            email: field("email"),
            refresh_token: field("refreshToken"),
        };
        Ok((session, IdToken::new(field("idToken"), &field("expiresIn"))))
    }

    /// Exchange the session's refresh token for a fresh ID token. Fails with
    /// [`Error::SessionExpired`] if the refresh token is no longer accepted.
    pub async fn refresh(
        &self,
        http: &reqwest::Client,
        session: &Session,
    ) -> Result<IdToken, Error> {
        let url = format!(
            "{}/v1/token?key={}",
            identity_url("securetoken.googleapis.com"),
            self.api_key
        );
        let body = identity_call(
            http.post(url).form(&[
                ("grant_type", "refresh_token"),
                ("refresh_token", session.refresh_token.as_str()),
            ]),
            Error::SessionExpired,
        )
        .await?;

        Ok(IdToken::new(
            body["id_token"].as_str().unwrap_or_default().into(),
            body["expires_in"].as_str().unwrap_or_default(),
        ))
    }
}

/// Base URL of a Google identity API, or of the Auth emulator.
fn identity_url(api: &str) -> String {
    match EMULATOR_HOST {
        Some(host) => format!("http://{host}/{api}"),
        None => format!("https://{api}"),
    }
}

/// Call an identity API. `refused` turns Firebase's refusal, as a readable
/// message, into an error.
async fn identity_call(
    request: reqwest::RequestBuilder,
    refused: fn(String) -> Error,
) -> Result<Value, Error> {
    let response = request.send().await?;
    let status = response.status();
    let body: Value = response.json().await?;
    if status.is_success() {
        Ok(body)
    } else {
        let code = body["error"]["message"].as_str().unwrap_or("unknown error");
        Err(refused(sign_in_message(code)))
    }
}

/// A readable message for an Identity Toolkit error code.
fn sign_in_message(code: &str) -> String {
    match code.split(' ').next().unwrap_or(code) {
        "INVALID_LOGIN_CREDENTIALS" | "INVALID_PASSWORD" | "EMAIL_NOT_FOUND" => {
            "wrong email or password".into()
        }
        "USER_DISABLED" => "this account is disabled".into(),
        "TOO_MANY_ATTEMPTS_TRY_LATER" => "too many attempts, try again later".into(),
        "TOKEN_EXPIRED" | "INVALID_REFRESH_TOKEN" | "USER_NOT_FOUND" => {
            "your session has expired, sign in again".into()
        }
        _ => code.to_lowercase().replace('_', " "),
    }
}

/// A short-lived token for the knife API.
#[derive(Debug, Clone, PartialEq)]
pub struct IdToken {
    pub token: String,
    /// `Date.now()` after which the token is no longer accepted.
    expires_at: f64,
}

impl IdToken {
    fn new(token: String, expires_in: &str) -> Self {
        let seconds: f64 = expires_in.parse().unwrap_or(3600.0);
        Self {
            token,
            expires_at: js_sys::Date::now() + seconds * 1000.0,
        }
    }

    /// Whether the token is still good for a request.
    pub fn is_fresh(&self) -> bool {
        js_sys::Date::now() + EXPIRY_MARGIN_MS < self.expires_at
    }
}

/// A signed-in user, as remembered across reloads.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Session {
    pub email: String,
    refresh_token: String,
}

impl Session {
    /// The session saved by a previous visit, if any.
    pub fn restore() -> Option<Self> {
        let text = storage()?.get_item(STORAGE_KEY).ok()??;
        serde_json::from_str(&text).ok()
    }

    /// Remember the session across reloads. Failures are ignored: the user
    /// then signs in again on the next visit.
    pub fn save(&self) {
        if let (Some(storage), Ok(text)) = (storage(), serde_json::to_string(self)) {
            let _ = storage.set_item(STORAGE_KEY, &text);
        }
    }

    pub fn forget() {
        if let Some(storage) = storage() {
            let _ = storage.remove_item(STORAGE_KEY);
        }
    }
}

fn storage() -> Option<web_sys::Storage> {
    web_sys::window()?.local_storage().ok()?
}
