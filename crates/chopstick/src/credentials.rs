//! What `chopstick login` remembers: the server, the project's web API key
//! and a Firebase refresh token. The file is readable by its owner only.

use crate::Error;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::Write;
use std::os::unix::fs::OpenOptionsExt;
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize)]
pub struct Credentials {
    pub url: String,
    pub api_key: String,
    pub email: String,
    pub refresh_token: String,
}

/// `$XDG_CONFIG_HOME/chopstick/credentials.json`, or under `~/.config`.
fn path() -> Result<PathBuf, Error> {
    let config = match std::env::var_os("XDG_CONFIG_HOME") {
        Some(dir) if !dir.is_empty() => PathBuf::from(dir),
        _ => PathBuf::from(std::env::var_os("HOME").ok_or(Error::NoHome)?).join(".config"),
    };
    Ok(config.join("chopstick").join("credentials.json"))
}

impl Credentials {
    pub fn load() -> Result<Self, Error> {
        let path = path()?;
        let text = fs::read_to_string(&path).map_err(|_| Error::NotLoggedIn)?;
        serde_json::from_str(&text).map_err(|e| Error::Credentials(path, e.to_string()))
    }

    pub fn save(&self) -> Result<PathBuf, Error> {
        let path = path()?;
        let io = |e: std::io::Error| Error::Credentials(path.clone(), e.to_string());

        if let Some(dir) = path.parent() {
            fs::create_dir_all(dir).map_err(io)?;
        }
        let mut file = fs::OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .mode(0o600)
            .open(&path)
            .map_err(io)?;
        let json = serde_json::to_string_pretty(self).expect("credentials serialize");
        file.write_all(json.as_bytes()).map_err(io)?;
        Ok(path)
    }

    /// Forget the stored credentials. Not an error if there are none.
    pub fn remove() -> Result<(), Error> {
        let path = path()?;
        match fs::remove_file(&path) {
            Err(e) if e.kind() != std::io::ErrorKind::NotFound => {
                Err(Error::Credentials(path, e.to_string()))
            }
            _ => Ok(()),
        }
    }
}
