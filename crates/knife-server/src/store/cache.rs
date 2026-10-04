//! An in-memory copy of the recipes, ingredients and labels, so a read costs
//! one Firestore document read instead of one per document returned.
//!
//! Every write transaction increments the `meta/version` document. A read
//! first fetches that version: when the copy is at least as recent, it is
//! served; otherwise the three collections are reloaded. Writes made by this
//! instance are applied to the copy as they commit, so only writes from
//! another instance cause a reload.
//!
//! Changes made outside knife-server, such as in the Firebase console, do not
//! bump the version and are not seen until the next restart.

use super::{INGREDIENTS, LABELS, RECIPES, Result, StoreError, StoredRecipe, get, label_doc_id};
use firestore::{FirestoreConsistencySelector, FirestoreTransactionOptions};
use firestore::{FirestoreDb, FirestoreTransaction, FirestoreTransactionMode};
use knife_core::{Ingredient, Label, Recipe, prefix_bounds};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use std::sync::Arc;
use tokio::sync::{Mutex, RwLock};

const META: &str = "meta";
const VERSION: &str = "version";

#[derive(Debug, Default, Serialize, Deserialize)]
struct Version {
    version: i64,
}

/// The version of the stored data, 0 before the first write.
async fn read_version(db: &FirestoreDb) -> Result<i64> {
    let found: Option<Version> = get(db, META, VERSION).await?;
    Ok(found.unwrap_or_default().version)
}

/// The cached collections at one version, keyed by document id.
#[derive(Debug, Clone, Default)]
pub(super) struct Snapshot {
    version: i64,
    pub recipes: BTreeMap<String, Recipe>,
    pub ingredients: BTreeMap<String, Ingredient>,
    pub labels: BTreeMap<String, Label>,
}

/// A record found by its simple name.
pub(super) trait Named {
    fn simple_name(&self) -> &str;
}

impl Named for Recipe {
    fn simple_name(&self) -> &str {
        &self.simple_name
    }
}

impl Named for Ingredient {
    fn simple_name(&self) -> &str {
        &self.simple_name
    }
}

impl Named for Label {
    fn simple_name(&self) -> &str {
        &self.simple_name
    }
}

/// Records whose simple name starts with the simplified `prefix`, sorted by
/// it.
pub(super) fn with_prefix<'a, T: Named>(docs: &'a BTreeMap<String, T>, prefix: &str) -> Vec<&'a T> {
    let (start, end) = prefix_bounds(prefix);
    let mut found: Vec<&T> = docs
        .values()
        .filter(|d| (start.as_str()..end.as_str()).contains(&d.simple_name()))
        .collect();
    found.sort_by(|a, b| a.simple_name().cmp(b.simple_name()));
    found
}

impl Snapshot {
    /// Read every cached collection, consistently.
    async fn load(db: &FirestoreDb) -> Result<Self> {
        let mut options = FirestoreTransactionOptions::new();
        options.mode = FirestoreTransactionMode::ReadOnly;
        let tx = db.begin_transaction_with_options(options).await?;
        let db = db.clone_with_consistency_selector(FirestoreConsistencySelector::Transaction(
            tx.transaction_id().clone(),
        ));

        let loaded = async {
            let version = read_version(&db).await?;
            let recipes: Vec<StoredRecipe> = all(&db, RECIPES).await?;
            let ingredients: Vec<Ingredient> = all(&db, INGREDIENTS).await?;
            let labels: Vec<Label> = all(&db, LABELS).await?;
            Ok::<_, StoreError>(Self {
                version,
                recipes: recipes
                    .into_iter()
                    .map(|s| (s.recipe.id.0.clone(), s.recipe))
                    .collect(),
                ingredients: ingredients
                    .into_iter()
                    .map(|i| (i.id.0.clone(), i))
                    .collect(),
                labels: labels
                    .into_iter()
                    .map(|l| (label_doc_id(&l.simple_name), l))
                    .collect(),
            })
        }
        .await;
        tx.rollback().await.ok();
        let loaded = loaded?;

        tracing::info!(
            version = loaded.version,
            recipes = loaded.recipes.len(),
            ingredients = loaded.ingredients.len(),
            labels = loaded.labels.len(),
            "loaded cache"
        );
        Ok(loaded)
    }

    fn apply(&mut self, change: &Change) -> Result<(), serde_json::Error> {
        fn set<T>(docs: &mut BTreeMap<String, T>, id: &str, doc: Option<T>) {
            match doc {
                Some(doc) => docs.insert(id.into(), doc),
                None => docs.remove(id),
            };
        }
        fn parse<T: serde::de::DeserializeOwned>(
            doc: &Option<Value>,
        ) -> Result<Option<T>, serde_json::Error> {
            doc.clone().map(serde_json::from_value).transpose()
        }

        match change.collection {
            RECIPES => {
                let doc = parse::<StoredRecipe>(&change.doc)?.map(|s| s.recipe);
                set(&mut self.recipes, &change.id, doc);
            }
            INGREDIENTS => set(&mut self.ingredients, &change.id, parse(&change.doc)?),
            LABELS => set(&mut self.labels, &change.id, parse(&change.doc)?),
            // Name reservations are only read in transactions.
            _ => {}
        }
        Ok(())
    }
}

async fn all<T>(db: &FirestoreDb, collection: &str) -> Result<Vec<T>>
where
    T: serde::de::DeserializeOwned + Send,
{
    Ok(db.fluent().select().from(collection).obj().query().await?)
}

/// A document written by a transaction; `doc` is `None` for a delete.
#[derive(Debug)]
struct Change {
    collection: &'static str,
    id: String,
    doc: Option<Value>,
}

/// The changes of a committed transaction, taking the data from version
/// `previous` to `previous + 1`.
pub(super) struct Committed {
    previous: i64,
    changes: Vec<Change>,
}

/// A Firestore transaction that remembers its writes, to apply them to the
/// cache once committed.
pub(crate) struct Tx<'a> {
    inner: FirestoreTransaction<'a>,
    changes: Vec<Change>,
}

impl<'a> Tx<'a> {
    pub(super) fn new(inner: FirestoreTransaction<'a>) -> Self {
        Self {
            inner,
            changes: Vec::new(),
        }
    }

    pub(super) fn transaction_id(&self) -> &firestore::FirestoreTransactionId {
        self.inner.transaction_id()
    }

    pub(super) fn inner(&mut self) -> &mut FirestoreTransaction<'a> {
        &mut self.inner
    }

    pub(super) fn record<T: Serialize>(
        &mut self,
        collection: &'static str,
        id: &str,
        doc: Option<&T>,
    ) -> Result<()> {
        self.changes.push(Change {
            collection,
            id: id.into(),
            doc: doc.map(serde_json::to_value).transpose()?,
        });
        Ok(())
    }

    /// Bump the version if anything was written, then commit. `db` reads in
    /// this transaction.
    pub(super) async fn commit(mut self, db: &FirestoreDb) -> Result<Option<Committed>> {
        if self.changes.is_empty() {
            self.inner.commit().await?;
            return Ok(None);
        }

        let previous = match read_version(db).await {
            Ok(version) => version,
            Err(err) => {
                self.inner.rollback().await.ok();
                return Err(err);
            }
        };
        db.fluent()
            .update()
            .in_col(META)
            .document_id(VERSION)
            .object(&Version {
                version: previous + 1,
            })
            .add_to_transaction(&mut self.inner)?;
        self.inner.commit().await?;

        Ok(Some(Committed {
            previous,
            changes: self.changes,
        }))
    }

    pub(super) async fn rollback(self) {
        self.inner.rollback().await.ok();
    }
}

#[derive(Default)]
pub(super) struct Cache {
    snapshot: RwLock<Option<Arc<Snapshot>>>,
    /// Held while reloading, so concurrent reads wait for one reload.
    reloading: Mutex<()>,
}

impl Cache {
    /// The cached data, reloaded first if Firestore has changed since.
    pub async fn current(&self, db: &FirestoreDb) -> Result<Arc<Snapshot>> {
        let version = read_version(db).await?;
        if let Some(snapshot) = self.at_least(version).await {
            return Ok(snapshot);
        }

        let _reloading = self.reloading.lock().await;
        if let Some(snapshot) = self.at_least(version).await {
            return Ok(snapshot);
        }
        let loaded = Arc::new(Snapshot::load(db).await?);
        let mut slot = self.snapshot.write().await;
        if slot.as_ref().is_none_or(|s| s.version < loaded.version) {
            *slot = Some(loaded.clone());
        }
        Ok(loaded)
    }

    async fn at_least(&self, version: i64) -> Option<Arc<Snapshot>> {
        self.snapshot
            .read()
            .await
            .as_ref()
            .filter(|s| s.version >= version)
            .cloned()
    }

    /// Apply a committed transaction, if the cache was at the version it
    /// started from. Otherwise the next read reloads.
    pub async fn committed(&self, committed: Committed) {
        let mut slot = self.snapshot.write().await;
        let Some(current) = slot.as_mut().filter(|s| s.version == committed.previous) else {
            return;
        };

        let snapshot = Arc::make_mut(current);
        let applied = committed.changes.iter().try_for_each(|c| snapshot.apply(c));
        match applied {
            Ok(()) => snapshot.version = committed.previous + 1,
            Err(err) => {
                tracing::warn!("dropping the cache, a write could not be applied: {err}");
                *slot = None;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use knife_core::{Classification, IngredientId, RecipeId, UserId};

    fn recipe(id: &str, simple_name: &str) -> Recipe {
        Recipe {
            id: RecipeId(id.into()),
            name: simple_name.into(),
            simple_name: simple_name.into(),
            author: String::new(),
            directions: String::new(),
            information: String::new(),
            requirements: BTreeMap::new(),
            dependencies: BTreeMap::new(),
            tags: ["dessert".to_owned()].into(),
            classification: Classification::default(),
            created_by: UserId::from("alice"),
            updated_by: UserId::from("alice"),
        }
    }

    fn put<T: Serialize>(collection: &'static str, id: &str, doc: &T) -> Change {
        Change {
            collection,
            id: id.into(),
            doc: Some(serde_json::to_value(doc).unwrap()),
        }
    }

    #[test]
    fn writes_are_applied() {
        let mut snapshot = Snapshot::default();
        let tart = recipe("r1", "tart");
        let butter = Ingredient {
            id: IngredientId("i1".into()),
            name: "Butter".into(),
            simple_name: "butter".into(),
            classification: Classification::default(),
        };

        for change in [
            put(RECIPES, "r1", &StoredRecipe::from(&tart)),
            put(INGREDIENTS, "i1", &butter),
            put(
                super::super::NAMES,
                "recipe:tart",
                &serde_json::json!({ "id": "r1" }),
            ),
        ] {
            snapshot.apply(&change).unwrap();
        }
        assert_eq!(snapshot.recipes["r1"], tart);
        assert_eq!(snapshot.ingredients["i1"], butter);

        let removal = Change {
            collection: RECIPES,
            id: "r1".into(),
            doc: None,
        };
        snapshot.apply(&removal).unwrap();
        assert!(snapshot.recipes.is_empty());
    }

    #[test]
    fn prefix_matches_simple_names_in_order() {
        let recipes: BTreeMap<String, Recipe> = [
            recipe("a", "pate_brisee"),
            recipe("b", "pasta"),
            recipe("c", "pate"),
            recipe("d", "tarte"),
        ]
        .into_iter()
        .map(|r| (r.id.0.clone(), r))
        .collect();

        let names = |prefix| -> Vec<&str> {
            with_prefix(&recipes, prefix)
                .iter()
                .map(|r| r.simple_name.as_str())
                .collect()
        };
        assert_eq!(names("Pâte"), ["pate", "pate_brisee"]);
        assert_eq!(names(""), ["pasta", "pate", "pate_brisee", "tarte"]);
        assert!(names("x").is_empty());
    }
}
