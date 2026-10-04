//! Firestore storage.
//!
//! Collections:
//! - `recipes/{id}`: a [`Recipe`] with its requirements, dependencies and tags
//!   embedded, plus `ingredient_ids` and `requisite_ids` arrays so reverse
//!   lookups are `array-contains` queries.
//! - `ingredients/{id}`: an [`Ingredient`].
//! - `labels/label:{simple_name}`: a [`knife_core::Label`].
//! - `names/{kind}:{simple_name}`: one per recipe or ingredient name, so
//!   names stay unique; created and deleted in the same transaction as the
//!   record.
//! - `meta/version`: incremented by every write, to keep the [`cache`] current.
//!
//! Every write and the updates it causes elsewhere (name copies, label
//! counts, classifications) run in one transaction. Reads outside
//! transactions are served from the [`cache`].

mod cache;
mod ingredients;
mod labels;
mod loader;
mod recipes;

use cache::Cache;
pub(crate) use cache::Tx;
use firestore::errors::FirestoreError;
use firestore::{
    FirestoreDb, FirestoreTransactionId, FirestoreTransactionMode, FirestoreTransactionOptions,
};
use knife_core::{IngredientId, Recipe, RecipeId};
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use std::time::Duration;

pub const RECIPES: &str = "recipes";
pub const INGREDIENTS: &str = "ingredients";
pub const LABELS: &str = "labels";
pub const NAMES: &str = "names";

/// Attempts per transaction when Firestore aborts it for contention.
const MAX_ATTEMPTS: u32 = 5;

#[derive(Debug, thiserror::Error)]
pub enum StoreError {
    #[error("{0} not found")]
    NotFound(String),

    /// `existing` is the record already holding the name, if any, so clients
    /// can reuse it.
    #[error("{detail}")]
    Conflict {
        detail: String,
        existing: Option<serde_json::Value>,
    },

    #[error(transparent)]
    Rule(#[from] knife_core::Error),

    #[error(transparent)]
    Firestore(#[from] FirestoreError),

    #[error("could not record a write for the cache: {0}")]
    Cache(#[from] serde_json::Error),
}

impl StoreError {
    fn is_retryable(&self) -> bool {
        matches!(self, Self::Firestore(FirestoreError::DatabaseError(e)) if e.retry_possible)
    }
}

pub type Result<T, E = StoreError> = std::result::Result<T, E>;

pub struct Store {
    db: FirestoreDb,
    cache: Cache,
}

/// Run `$body` in a Firestore transaction, retrying when Firestore aborts it
/// for contention. Inside `$body`, `$db` reads within the transaction and
/// writes are queued on `$tx`, a [`Tx`], until commit; once committed they
/// are applied to the cache. `$body` must be safe to rerun.
macro_rules! in_transaction {
    ($store:expr, |$db:ident, $tx:ident| $body:expr) => {{
        let mut attempt = 1;
        let mut first_id = None;
        loop {
            let mut $tx = $crate::store::Tx::new(
                $store
                    .db
                    .begin_transaction_with_options($crate::store::transaction_options(
                        first_id.as_ref(),
                    ))
                    .await?,
            );
            first_id.get_or_insert_with(|| $tx.transaction_id().clone());
            let $db = $store.db.clone_with_consistency_selector(
                ::firestore::FirestoreConsistencySelector::Transaction(
                    $tx.transaction_id().clone(),
                ),
            );

            let result: $crate::store::Result<_> = async { $body }.await;
            let result = match result {
                Ok(value) => $tx.commit(&$db).await.map(|committed| (value, committed)),
                Err(err) => {
                    $tx.rollback().await;
                    Err(err)
                }
            };

            match result {
                Ok((value, committed)) => {
                    if let Some(committed) = committed {
                        $store.cache.committed(committed).await;
                    }
                    break Ok(value);
                }
                Err(err) if err.is_retryable() && attempt < $crate::store::MAX_ATTEMPTS => {
                    ::tracing::warn!(attempt, "transaction aborted, retrying: {err}");
                    $crate::store::backoff(attempt).await;
                    attempt += 1;
                }
                Err(err) => break Err(err),
            }
        }
    }};
}
pub(crate) use in_transaction;

/// A retry names the first attempt's transaction, so Firestore keeps its
/// place in the lock queue instead of starving it.
fn transaction_options(retrying: Option<&FirestoreTransactionId>) -> FirestoreTransactionOptions {
    let mut options = FirestoreTransactionOptions::new();
    if let Some(id) = retrying {
        options.mode = FirestoreTransactionMode::ReadWriteRetry(id.clone());
    }
    options
}

/// Exponential backoff with full jitter, so transactions that aborted each
/// other do not retry in lockstep.
async fn backoff(attempt: u32) {
    let cap = (100u64 << attempt.min(5)).min(2000);
    let jitter = uuid::Uuid::new_v4().as_u128() % u128::from(cap);
    tokio::time::sleep(Duration::from_millis(jitter as u64)).await;
}

impl Store {
    pub fn new(db: FirestoreDb) -> Self {
        Self {
            db,
            cache: Cache::default(),
        }
    }
}

/// The recipe document: a [`Recipe`] plus arrays for reverse lookups.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct StoredRecipe {
    #[serde(flatten)]
    recipe: Recipe,
    ingredient_ids: Vec<IngredientId>,
    requisite_ids: Vec<RecipeId>,
}

impl From<&Recipe> for StoredRecipe {
    fn from(recipe: &Recipe) -> Self {
        Self {
            ingredient_ids: recipe.requirements.keys().cloned().collect(),
            requisite_ids: recipe.dependencies.keys().cloned().collect(),
            recipe: recipe.clone(),
        }
    }
}

/// A reservation of a name by a recipe or ingredient.
#[derive(Debug, Clone, Serialize, Deserialize)]
struct NameDoc {
    id: String,
}

#[derive(Clone, Copy)]
enum NameKind {
    Recipe,
    Ingredient,
}

fn name_doc_id(kind: NameKind, simple_name: &str) -> String {
    let kind = match kind {
        NameKind::Recipe => "recipe",
        NameKind::Ingredient => "ingredient",
    };
    format!("{kind}:{simple_name}")
}

fn label_doc_id(simple_name: &str) -> String {
    format!("label:{simple_name}")
}

fn new_id() -> String {
    uuid::Uuid::new_v4().simple().to_string()
}

async fn get<T>(db: &FirestoreDb, collection: &str, id: &str) -> Result<Option<T>>
where
    T: DeserializeOwned + Send,
{
    Ok(db
        .fluent()
        .select()
        .by_id_in(collection)
        .obj()
        .one(id)
        .await?)
}

/// Documents whose array `field` contains `value`.
async fn containing<T, V>(
    db: &FirestoreDb,
    collection: &str,
    field: &str,
    value: V,
) -> Result<Vec<T>>
where
    T: DeserializeOwned + Send,
    V: Serialize,
{
    Ok(db
        .fluent()
        .select()
        .from(collection)
        .filter(|q| q.field(field).array_contains(&value))
        .obj()
        .query()
        .await?)
}

/// Queue a whole-document write.
fn put<T>(db: &FirestoreDb, tx: &mut Tx, collection: &'static str, id: &str, doc: &T) -> Result<()>
where
    T: Serialize + DeserializeOwned + Send + Sync,
{
    db.fluent()
        .update()
        .in_col(collection)
        .document_id(id)
        .object(doc)
        .add_to_transaction(tx.inner())?;
    tx.record(collection, id, Some(doc))
}

fn put_recipe(db: &FirestoreDb, tx: &mut Tx, recipe: &Recipe) -> Result<()> {
    put(db, tx, RECIPES, &recipe.id.0, &StoredRecipe::from(recipe))
}

fn remove(db: &FirestoreDb, tx: &mut Tx, collection: &'static str, id: &str) -> Result<()> {
    db.fluent()
        .delete()
        .from(collection)
        .document_id(id)
        .add_to_transaction(tx.inner())?;
    tx.record::<()>(collection, id, None)
}

/// The id holding a name, if another record than `owner` holds it.
async fn name_taken_by(
    db: &FirestoreDb,
    kind: NameKind,
    simple_name: &str,
    owner: Option<&str>,
) -> Result<Option<String>> {
    let held: Option<NameDoc> = get(db, NAMES, &name_doc_id(kind, simple_name)).await?;
    Ok(held.map(|n| n.id).filter(|id| Some(id.as_str()) != owner))
}

/// Move a name reservation from `old` to `new` simple name, both held by
/// `owner`. A no-op when the simple name does not change.
fn move_name(
    db: &FirestoreDb,
    tx: &mut Tx,
    kind: NameKind,
    old: &str,
    new: &str,
    owner: &str,
) -> Result<()> {
    if old != new {
        remove(db, tx, NAMES, &name_doc_id(kind, old))?;
        put(
            db,
            tx,
            NAMES,
            &name_doc_id(kind, new),
            &NameDoc { id: owner.into() },
        )?;
    }
    Ok(())
}
