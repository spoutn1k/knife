//! Family membership. A valid Firebase account is not enough: its uid must
//! also have a document in the `members` collection, which admins manage.
//! Members can only read, unless their document sets `editor: true`.

use firestore::FirestoreDb;
use firestore::errors::FirestoreError;
use knife_core::UserId;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::{Duration, Instant};
use tokio::sync::Mutex;

pub const COLLECTION: &str = "members";

/// Positive lookups are cached this long, so removing a member or changing
/// their rights from another server instance takes effect within this delay.
const CACHE_TTL: Duration = Duration::from_secs(300);

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Member {
    pub display_name: String,
    /// May change the recipe book. Read-only when absent.
    #[serde(default)]
    pub editor: bool,
    /// May manage members.
    #[serde(default)]
    pub admin: bool,
}

/// A member document with its id, which is the member's uid.
#[derive(Deserialize)]
struct Listed {
    #[serde(alias = "_firestore_id")]
    uid: UserId,
    #[serde(flatten)]
    member: Member,
}

pub enum Members {
    Firestore {
        db: FirestoreDb,
        cache: Mutex<HashMap<UserId, (Instant, Member)>>,
    },
    /// Kept in memory, for tests.
    Fixed(Mutex<HashMap<UserId, Member>>),
}

impl Members {
    pub fn firestore(db: FirestoreDb) -> Self {
        Self::Firestore {
            db,
            cache: Mutex::default(),
        }
    }

    pub fn fixed(members: impl IntoIterator<Item = (UserId, Member)>) -> Self {
        Self::Fixed(Mutex::new(members.into_iter().collect()))
    }

    /// The member with this uid, if any.
    pub async fn get(&self, uid: &UserId) -> Result<Option<Member>, FirestoreError> {
        match self {
            Self::Fixed(members) => Ok(members.lock().await.get(uid).cloned()),
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

    /// Every member, by uid.
    pub async fn list(&self) -> Result<Vec<(UserId, Member)>, FirestoreError> {
        match self {
            Self::Fixed(members) => Ok(members
                .lock()
                .await
                .iter()
                .map(|(uid, m)| (uid.clone(), m.clone()))
                .collect()),
            Self::Firestore { db, .. } => {
                let listed: Vec<Listed> =
                    db.fluent().select().from(COLLECTION).obj().query().await?;
                Ok(listed.into_iter().map(|l| (l.uid, l.member)).collect())
            }
        }
    }

    /// Add a member or replace their document.
    pub async fn set(&self, uid: &UserId, member: &Member) -> Result<(), FirestoreError> {
        match self {
            Self::Fixed(members) => {
                members.lock().await.insert(uid.clone(), member.clone());
            }
            Self::Firestore { db, cache } => {
                let _: Member = db
                    .fluent()
                    .update()
                    .in_col(COLLECTION)
                    .document_id(&uid.0)
                    .object(member)
                    .execute()
                    .await?;
                cache
                    .lock()
                    .await
                    .insert(uid.clone(), (Instant::now(), member.clone()));
            }
        }
        Ok(())
    }

    pub async fn remove(&self, uid: &UserId) -> Result<(), FirestoreError> {
        match self {
            Self::Fixed(members) => {
                members.lock().await.remove(uid);
            }
            Self::Firestore { db, cache } => {
                db.fluent()
                    .delete()
                    .from(COLLECTION)
                    .document_id(&uid.0)
                    .execute()
                    .await?;
                cache.lock().await.remove(uid);
            }
        }
        Ok(())
    }
}
