//! Family membership. A valid Firebase account is not enough: its uid must
//! also have a document in the `members` collection, added by hand.

use firestore::FirestoreDb;
use knife_core::UserId;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::time::{Duration, Instant};
use tokio::sync::Mutex;

pub const COLLECTION: &str = "members";

/// Positive lookups are cached this long, so removing a member takes effect
/// within this delay.
const CACHE_TTL: Duration = Duration::from_secs(300);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Member {
    pub display_name: String,
}

pub enum Members {
    Firestore {
        db: FirestoreDb,
        cache: Mutex<HashMap<UserId, Instant>>,
    },
    /// A fixed list, for tests.
    Fixed(HashSet<UserId>),
}

impl Members {
    pub fn firestore(db: FirestoreDb) -> Self {
        Self::Firestore {
            db,
            cache: Mutex::default(),
        }
    }

    pub async fn contains(&self, uid: &UserId) -> Result<bool, firestore::errors::FirestoreError> {
        match self {
            Self::Fixed(uids) => Ok(uids.contains(uid)),
            Self::Firestore { db, cache } => {
                if cache
                    .lock()
                    .await
                    .get(uid)
                    .is_some_and(|t| t.elapsed() < CACHE_TTL)
                {
                    return Ok(true);
                }

                let member: Option<Member> = db
                    .fluent()
                    .select()
                    .by_id_in(COLLECTION)
                    .obj()
                    .one(&uid.0)
                    .await?;

                if member.is_some() {
                    cache.lock().await.insert(uid.clone(), Instant::now());
                }
                Ok(member.is_some())
            }
        }
    }
}
