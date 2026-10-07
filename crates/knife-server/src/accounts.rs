//! Firebase Auth accounts, managed through the Identity Toolkit admin API.
//!
//! The Auth emulator serves the same API and takes `Bearer owner` as an
//! admin token. In production, the token is the service account's, from the
//! metadata server; it needs the Firebase Authentication Admin role.

use knife_core::UserId;
use serde::Deserialize;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use std::time::{Duration, Instant};
use tokio::sync::Mutex;

const GOOGLE_API: &str = "https://identitytoolkit.googleapis.com";

const METADATA_TOKEN_URL: &str =
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token";

/// Access tokens are refreshed this long before they expire.
const TOKEN_MARGIN: Duration = Duration::from_secs(60);

#[derive(Debug, thiserror::Error)]
pub enum AccountError {
    /// Refused by Identity Toolkit, such as `EMAIL_EXISTS` or
    /// `WEAK_PASSWORD : Password should be at least 6 characters`.
    #[error("{0}")]
    Refused(String),
    #[error("Identity Toolkit call failed: {0}")]
    Http(#[from] reqwest::Error),
    #[error("unexpected Identity Toolkit response: {0}")]
    Response(String),
}

impl AccountError {
    /// The code of a refusal, such as `EMAIL_EXISTS`, without its
    /// explanation.
    pub fn code(&self) -> Option<&str> {
        match self {
            Self::Refused(message) => message.split(" : ").next(),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Account {
    pub uid: UserId,
    pub email: Option<String>,
}

pub struct Accounts {
    http: reqwest::Client,
    base: String,
    project_id: String,
    credentials: Credentials,
}

enum Credentials {
    Emulator,
    /// The cached access token and when to refresh it.
    Metadata(Mutex<Option<(String, Instant)>>),
}

impl Accounts {
    /// Manage the project's accounts, as the service account.
    pub fn google(project_id: impl Into<String>) -> Self {
        Self {
            http: reqwest::Client::new(),
            base: GOOGLE_API.into(),
            project_id: project_id.into(),
            credentials: Credentials::Metadata(Mutex::default()),
        }
    }

    /// Manage the Auth emulator's accounts. `host` is as in
    /// `FIREBASE_AUTH_EMULATOR_HOST`.
    pub fn emulator(project_id: impl Into<String>, host: &str) -> Self {
        Self {
            http: reqwest::Client::new(),
            base: format!("http://{host}/identitytoolkit.googleapis.com"),
            project_id: project_id.into(),
            credentials: Credentials::Emulator,
        }
    }

    pub async fn by_email(&self, email: &str) -> Result<Option<Account>, AccountError> {
        let found = self.lookup(json!({ "email": [email] })).await?;
        Ok(found.into_iter().next())
    }

    /// The accounts that still exist among `uids`.
    pub async fn by_uids(&self, uids: &[UserId]) -> Result<Vec<Account>, AccountError> {
        if uids.is_empty() {
            return Ok(vec![]);
        }
        self.lookup(json!({ "localId": uids })).await
    }

    pub async fn create(
        &self,
        email: &str,
        password: &str,
        display_name: &str,
    ) -> Result<UserId, AccountError> {
        #[derive(Deserialize)]
        #[serde(rename_all = "camelCase")]
        struct Created {
            local_id: String,
        }

        let body = json!({ "email": email, "password": password, "displayName": display_name });
        let created: Created = self.call("", body).await?;
        Ok(UserId(created.local_id))
    }

    pub async fn set_password(&self, uid: &UserId, password: &str) -> Result<(), AccountError> {
        let body = json!({ "localId": uid, "password": password });
        self.call::<Value>(":update", body).await?;
        Ok(())
    }

    /// Email the account a link to choose a new password, from the project's
    /// template. The Auth emulator only records the link.
    pub async fn send_password_reset(&self, email: &str) -> Result<(), AccountError> {
        let body = json!({ "requestType": "PASSWORD_RESET", "email": email });
        self.call::<Value>(":sendOobCode", body).await?;
        Ok(())
    }

    /// Delete an account. Deleting one that does not exist succeeds.
    pub async fn delete(&self, uid: &UserId) -> Result<(), AccountError> {
        match self
            .call::<Value>(":delete", json!({ "localId": uid }))
            .await
        {
            Err(e) if e.code() != Some("USER_NOT_FOUND") => Err(e),
            _ => Ok(()),
        }
    }

    async fn lookup(&self, body: Value) -> Result<Vec<Account>, AccountError> {
        #[derive(Deserialize)]
        struct Found {
            #[serde(default)]
            users: Vec<User>,
        }
        #[derive(Deserialize)]
        #[serde(rename_all = "camelCase")]
        struct User {
            local_id: String,
            email: Option<String>,
        }

        let found: Found = self.call(":lookup", body).await?;
        Ok(found
            .users
            .into_iter()
            .map(|u| Account {
                uid: UserId(u.local_id),
                email: u.email,
            })
            .collect())
    }

    /// `POST /v1/projects/{project}/accounts{method}`.
    async fn call<T: DeserializeOwned>(
        &self,
        method: &str,
        body: Value,
    ) -> Result<T, AccountError> {
        let url = format!(
            "{}/v1/projects/{}/accounts{method}",
            self.base, self.project_id
        );
        let response = self
            .http
            .post(url)
            .bearer_auth(self.token().await?)
            .json(&body)
            .send()
            .await?;

        let status = response.status();
        let text = response.text().await?;
        if !status.is_success() {
            // Bad input is a 400 naming the problem; anything else, such as
            // a missing permission, is the server's.
            let error: Value = serde_json::from_str(&text).unwrap_or(Value::Null);
            return Err(match error["error"]["message"].as_str() {
                Some(message) if status == reqwest::StatusCode::BAD_REQUEST => {
                    AccountError::Refused(message.into())
                }
                _ => AccountError::Response(format!("{status}: {text}")),
            });
        }
        serde_json::from_str(&text).map_err(|e| AccountError::Response(e.to_string()))
    }

    async fn token(&self) -> Result<String, AccountError> {
        let cache = match &self.credentials {
            Credentials::Emulator => return Ok("owner".into()),
            Credentials::Metadata(cache) => cache,
        };

        let mut cache = cache.lock().await;
        if let Some((token, refresh)) = &*cache
            && Instant::now() < *refresh
        {
            return Ok(token.clone());
        }

        #[derive(Deserialize)]
        struct Token {
            access_token: String,
            expires_in: u64,
        }
        let token: Token = self
            .http
            .get(METADATA_TOKEN_URL)
            .header("Metadata-Flavor", "Google")
            .send()
            .await
            .and_then(reqwest::Response::error_for_status)?
            .json()
            .await?;

        let refresh =
            Instant::now() + Duration::from_secs(token.expires_in).saturating_sub(TOKEN_MARGIN);
        *cache = Some((token.access_token.clone(), refresh));
        Ok(token.access_token)
    }
}
