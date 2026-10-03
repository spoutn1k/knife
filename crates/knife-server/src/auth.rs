//! Firebase ID token verification.
//!
//! Tokens are RS256 JWTs signed by Google. The public keys are published as a
//! JWK set and rotate, so they are cached for as long as the response's
//! `Cache-Control: max-age` allows. The Auth emulator issues unsigned tokens,
//! which are accepted only in [`Verifier::emulator`] mode.

use base64::Engine;
use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use jsonwebtoken::jwk::JwkSet;
use jsonwebtoken::{Algorithm, DecodingKey, Validation};
use knife_core::UserId;
use serde::Deserialize;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::sync::RwLock;

const GOOGLE_JWKS_URL: &str =
    "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com";

/// Keys are refetched on an unknown `kid` at most this often.
const MIN_REFRESH: Duration = Duration::from_secs(60);

/// Allowed clock skew between Google and this server.
const LEEWAY: u64 = 60;

#[derive(Debug, thiserror::Error)]
pub enum TokenError {
    #[error("malformed token")]
    Malformed,
    #[error("token signed with an unknown key")]
    UnknownKey,
    #[error("invalid token: {0}")]
    Invalid(String),
    #[error("could not fetch Google signing keys: {0}")]
    KeyFetch(String),
}

#[derive(Debug, Clone, Deserialize)]
pub struct Claims {
    pub sub: String,
    pub aud: String,
    pub iss: String,
    pub exp: u64,
    pub auth_time: u64,
    pub email: Option<String>,
    #[serde(default)]
    pub email_verified: bool,
}

/// The signed-in user making a request.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CurrentUser {
    pub uid: UserId,
    pub email: Option<String>,
}

pub struct Verifier {
    project_id: String,
    mode: Mode,
}

enum Mode {
    Google(GoogleKeys),
    Emulator,
}

struct GoogleKeys {
    client: Option<reqwest::Client>,
    cache: RwLock<CachedKeys>,
}

struct CachedKeys {
    keys: JwkSet,
    fetched: Instant,
    expires: Instant,
}

impl Verifier {
    /// Verify tokens against Google's published keys.
    pub fn google(project_id: impl Into<String>) -> Self {
        let now = Instant::now();
        Self {
            project_id: project_id.into(),
            mode: Mode::Google(GoogleKeys {
                client: Some(reqwest::Client::new()),
                cache: RwLock::new(CachedKeys {
                    keys: JwkSet { keys: vec![] },
                    fetched: now - MIN_REFRESH,
                    expires: now,
                }),
            }),
        }
    }

    /// Verify tokens against a fixed key set, never fetching. For tests.
    pub fn with_keys(project_id: impl Into<String>, keys: JwkSet) -> Self {
        let now = Instant::now();
        Self {
            project_id: project_id.into(),
            mode: Mode::Google(GoogleKeys {
                client: None,
                cache: RwLock::new(CachedKeys {
                    keys,
                    fetched: now,
                    expires: now + Duration::from_secs(u32::MAX.into()),
                }),
            }),
        }
    }

    /// Accept the Auth emulator's unsigned tokens. Never use in production.
    pub fn emulator(project_id: impl Into<String>) -> Self {
        Self {
            project_id: project_id.into(),
            mode: Mode::Emulator,
        }
    }

    pub async fn verify(&self, token: &str) -> Result<CurrentUser, TokenError> {
        let claims = match &self.mode {
            Mode::Google(keys) => self.verify_signed(keys, token).await?,
            Mode::Emulator => decode_unsigned(token)?,
        };
        check_claims(&claims, &self.project_id, unix_now())?;

        Ok(CurrentUser {
            uid: UserId(claims.sub),
            email: claims.email.filter(|_| claims.email_verified),
        })
    }

    async fn verify_signed(&self, keys: &GoogleKeys, token: &str) -> Result<Claims, TokenError> {
        let header = jsonwebtoken::decode_header(token).map_err(|_| TokenError::Malformed)?;
        if header.alg != Algorithm::RS256 {
            return Err(TokenError::Invalid(format!("algorithm {:?}", header.alg)));
        }
        let kid = header.kid.ok_or(TokenError::Malformed)?;
        let key = keys.find(&kid).await?;

        let mut validation = Validation::new(Algorithm::RS256);
        validation.leeway = LEEWAY;
        validation.set_audience(&[&self.project_id]);
        validation.set_issuer(&[issuer(&self.project_id)]);
        validation.set_required_spec_claims(&["exp", "aud", "iss", "sub"]);

        jsonwebtoken::decode::<Claims>(token, &key, &validation)
            .map(|data| data.claims)
            .map_err(|e| TokenError::Invalid(e.to_string()))
    }
}

impl GoogleKeys {
    async fn find(&self, kid: &str) -> Result<DecodingKey, TokenError> {
        {
            let cache = self.cache.read().await;
            let fresh = Instant::now() < cache.expires;
            if let Some(jwk) = cache.keys.find(kid) {
                if fresh {
                    return DecodingKey::from_jwk(jwk).map_err(|_| TokenError::UnknownKey);
                }
            } else if fresh && cache.fetched.elapsed() < MIN_REFRESH {
                return Err(TokenError::UnknownKey);
            }
        }

        // Expired, or an unknown kid after a rotation: refetch.
        let Some(client) = &self.client else {
            return Err(TokenError::UnknownKey);
        };
        let mut cache = self.cache.write().await;
        if cache.fetched.elapsed() >= MIN_REFRESH || Instant::now() >= cache.expires {
            *cache = fetch_keys(client).await?;
        }
        let jwk = cache.keys.find(kid).ok_or(TokenError::UnknownKey)?;
        DecodingKey::from_jwk(jwk).map_err(|_| TokenError::UnknownKey)
    }
}

async fn fetch_keys(client: &reqwest::Client) -> Result<CachedKeys, TokenError> {
    let fetch_error = |e: reqwest::Error| TokenError::KeyFetch(e.to_string());

    let response = client
        .get(GOOGLE_JWKS_URL)
        .send()
        .await
        .and_then(reqwest::Response::error_for_status)
        .map_err(fetch_error)?;
    let max_age = response
        .headers()
        .get(reqwest::header::CACHE_CONTROL)
        .and_then(|v| v.to_str().ok())
        .and_then(max_age)
        .unwrap_or(Duration::from_secs(3600));
    let keys = response.json::<JwkSet>().await.map_err(fetch_error)?;

    let now = Instant::now();
    Ok(CachedKeys {
        keys,
        fetched: now,
        expires: now + max_age,
    })
}

fn max_age(cache_control: &str) -> Option<Duration> {
    cache_control
        .split(',')
        .find_map(|d| d.trim().strip_prefix("max-age="))
        .and_then(|s| s.parse().ok())
        .map(Duration::from_secs)
}

fn issuer(project_id: &str) -> String {
    format!("https://securetoken.google.com/{project_id}")
}

fn unix_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("clock after 1970")
        .as_secs()
}

/// Decode an Auth emulator token, which has `"alg": "none"` and no signature.
fn decode_unsigned(token: &str) -> Result<Claims, TokenError> {
    let mut parts = token.split('.');
    let (Some(header), Some(payload)) = (parts.next(), parts.next()) else {
        return Err(TokenError::Malformed);
    };
    let decode = |part: &str| {
        URL_SAFE_NO_PAD
            .decode(part)
            .map_err(|_| TokenError::Malformed)
    };

    #[derive(Deserialize)]
    struct Header {
        alg: String,
    }
    let header: Header =
        serde_json::from_slice(&decode(header)?).map_err(|_| TokenError::Malformed)?;
    if header.alg != "none" {
        return Err(TokenError::Invalid(format!("algorithm {}", header.alg)));
    }

    serde_json::from_slice(&decode(payload)?).map_err(|_| TokenError::Malformed)
}

/// Checks Firebase requires on every token, signed or not.
fn check_claims(claims: &Claims, project_id: &str, now: u64) -> Result<(), TokenError> {
    let invalid = |reason: &str| Err(TokenError::Invalid(reason.into()));

    if claims.aud != project_id {
        return invalid("wrong audience");
    }
    if claims.iss != issuer(project_id) {
        return invalid("wrong issuer");
    }
    if claims.sub.is_empty() {
        return invalid("empty subject");
    }
    if claims.exp + LEEWAY <= now {
        return invalid("expired");
    }
    if claims.auth_time > now + LEEWAY {
        return invalid("authenticated in the future");
    }
    Ok(())
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use jsonwebtoken::{EncodingKey, Header};
    use serde_json::{Value, json};

    pub const PROJECT: &str = "knife-test";

    pub fn test_verifier() -> Verifier {
        let jwks = serde_json::from_str(include_str!("../testdata/test-jwks.json")).unwrap();
        Verifier::with_keys(PROJECT, jwks)
    }

    pub fn claims(uid: &str) -> Value {
        let now = unix_now();
        json!({
            "sub": uid,
            "aud": PROJECT,
            "iss": issuer(PROJECT),
            "iat": now,
            "exp": now + 3600,
            "auth_time": now,
            "email": format!("{uid}@example.com"),
            "email_verified": true,
        })
    }

    pub fn sign(claims: &Value, kid: &str) -> String {
        let key = EncodingKey::from_rsa_pem(include_bytes!("../testdata/test-key.pem")).unwrap();
        let mut header = Header::new(Algorithm::RS256);
        header.kid = Some(kid.into());
        jsonwebtoken::encode(&header, claims, &key).unwrap()
    }

    fn unsigned(claims: &Value) -> String {
        let header = URL_SAFE_NO_PAD.encode(r#"{"alg":"none","typ":"JWT"}"#);
        let payload = URL_SAFE_NO_PAD.encode(claims.to_string());
        format!("{header}.{payload}.")
    }

    #[tokio::test]
    async fn valid_token_is_accepted() {
        let user = test_verifier()
            .verify(&sign(&claims("alice"), "test-key"))
            .await
            .unwrap();

        assert_eq!(user.uid, UserId::from("alice"));
        assert_eq!(user.email.as_deref(), Some("alice@example.com"));
    }

    #[tokio::test]
    async fn unverified_email_is_dropped() {
        let mut claims = claims("alice");
        claims["email_verified"] = json!(false);

        let user = test_verifier()
            .verify(&sign(&claims, "test-key"))
            .await
            .unwrap();
        assert_eq!(user.email, None);
    }

    #[tokio::test]
    async fn unknown_key_is_rejected() {
        let result = test_verifier()
            .verify(&sign(&claims("alice"), "other-key"))
            .await;
        assert!(matches!(result, Err(TokenError::UnknownKey)));
    }

    #[tokio::test]
    async fn tampered_token_is_rejected() {
        let token = sign(&claims("alice"), "test-key");
        let mut parts: Vec<&str> = token.split('.').collect();
        let forged = URL_SAFE_NO_PAD.encode(claims("mallory").to_string());
        parts[1] = &forged;

        let result = test_verifier().verify(&parts.join(".")).await;
        assert!(matches!(result, Err(TokenError::Invalid(_))));
    }

    #[tokio::test]
    async fn other_project_is_rejected() {
        let mut claims = claims("alice");
        claims["aud"] = json!("someone-else");

        let result = test_verifier().verify(&sign(&claims, "test-key")).await;
        assert!(matches!(result, Err(TokenError::Invalid(_))));
    }

    #[tokio::test]
    async fn expired_token_is_rejected() {
        let mut claims = claims("alice");
        claims["exp"] = json!(unix_now() - 3600);

        let result = test_verifier().verify(&sign(&claims, "test-key")).await;
        assert!(matches!(result, Err(TokenError::Invalid(_))));
    }

    #[tokio::test]
    async fn unsigned_token_is_rejected_outside_emulator() {
        let result = test_verifier().verify(&unsigned(&claims("alice"))).await;
        assert!(matches!(result, Err(TokenError::Malformed)));
    }

    #[tokio::test]
    async fn emulator_accepts_unsigned_tokens() {
        let user = Verifier::emulator(PROJECT)
            .verify(&unsigned(&claims("alice")))
            .await
            .unwrap();
        assert_eq!(user.uid, UserId::from("alice"));
    }

    #[tokio::test]
    async fn emulator_still_checks_claims() {
        let mut claims = claims("alice");
        claims["aud"] = json!("someone-else");

        let result = Verifier::emulator(PROJECT).verify(&unsigned(&claims)).await;
        assert!(matches!(result, Err(TokenError::Invalid(_))));
    }

    #[tokio::test]
    async fn emulator_rejects_signed_algorithms() {
        let result = Verifier::emulator(PROJECT)
            .verify(&sign(&claims("alice"), "test-key"))
            .await;
        assert!(matches!(result, Err(TokenError::Invalid(_))));
    }

    #[test]
    fn max_age_is_parsed() {
        assert_eq!(
            max_age("public, max-age=19302, must-revalidate, no-transform"),
            Some(Duration::from_secs(19302))
        );
        assert_eq!(max_age("no-cache"), None);
    }
}
