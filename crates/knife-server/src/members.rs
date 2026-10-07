//! Family membership. A valid Firebase account is not enough: its uid must
//! also have a document in the `members` collection, added by hand. Members
//! can only read, unless their document sets `editor: true`.

use firestore::FirestoreDb;
use knife_core::UserId;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::{Duration, Instant};
use tokio::sync::Mutex;

pub const COLLECTION: &str = "members";

/// Positive lookups are cached this long, so removing a member or changing
/// their rights takes effect within this delay.
const CACHE_TTL: Duration = Duration::from_secs(300);

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Member {
    pub display_name: String,
    /// May change the recipe book. Read-only when absent.
    #[serde(default)]
    pub editor: bool,
}

pub enum Members {
    Firestore {
        db: FirestoreDb,
        cache: Mutex<HashMap<UserId, (Instant, Member)>>,
    },
    /// A fixed list, for tests.
    Fixed(HashMap<UserId, Member>),
}

impl Members {
    pub fn firestore(db: FirestoreDb) -> Self {
        Self::Firestore {
            db,
            cache: Mutex::default(),
        }
    }

    /// The member with this uid, if any.
    pub async fn get(
        &self,
        uid: &UserId,
    ) -> Result<Option<Member>, firestore::errors::FirestoreError> {
        match self {
            Self::Fixed(members) => Ok(members.get(uid).cloned()),
            Self::Firestore { db, cache } => {
                if let Some((t, member)) = cache.lock().await.get(uid)
                    && t.elapsed() < CACHE_TTL
                {
                    return Ok(Some(member.clone()));
                }

                let member: Option<Member> = db
                    .fluent()
                    .select()
                    .by_id_in(COLLECTION)
                    .obj()
                    .one(&uid.0)
                    .await?;

                if let Some(member) = &member {
                    cache
                        .lock()
                        .await
                        .insert(uid.clone(), (Instant::now(), member.clone()));
                }
                Ok(member)
            }
        }
    }
}
