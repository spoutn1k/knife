use super::cache::with_prefix;
use super::loader::Recipes;
use super::{
    LABELS, Result, Store, StoreError, Tx, get, in_transaction, label_doc_id, put, remove,
};
use firestore::FirestoreDb;
use knife_core::input::LabelPatch;
use knife_core::{Label, LabelDetails, Recipe, simplify};

impl Store {
    pub async fn list_labels(&self, prefix: &str) -> Result<Vec<Label>> {
        let cached = self.cache.current(&self.db).await?;
        Ok(with_prefix(&cached.labels, prefix)
            .into_iter()
            .cloned()
            .collect())
    }

    pub async fn get_label(&self, label: &str) -> Result<LabelDetails> {
        let simple_name = simplify(label);
        let cached = self.cache.current(&self.db).await?;
        let label = cached
            .labels
            .get(&label_doc_id(&simple_name))
            .cloned()
            .ok_or_else(|| StoreError::NotFound(format!("label {simple_name}")))?;

        Ok(LabelDetails {
            recipes: cached
                .recipes
                .values()
                .filter(|r| r.tags.contains(&label.simple_name))
                .map(Recipe::summary)
                .collect(),
            label,
        })
    }

    /// Rename a label. When its simple name changes, every tagged recipe is
    /// retagged.
    pub async fn update_label(&self, label: &str, patch: &LabelPatch) -> Result<Label> {
        let new_name = patch.validate()?;
        let old_simple_name = simplify(label);

        in_transaction!(self, |db, tx| {
            let mut label = require(&db, &old_simple_name).await?;

            if new_name.simple_name != old_simple_name {
                if let Some(existing) =
                    get::<Label>(&db, LABELS, &label_doc_id(&new_name.simple_name)).await?
                {
                    return Err(StoreError::Conflict {
                        detail: "a label with this name already exists".into(),
                        existing: Some(serde_json::json!(existing)),
                    });
                }

                let mut recipes = Recipes::default();
                for id in recipes.containing(&db, "tags", &old_simple_name).await? {
                    let tags = &mut recipes.edit(&id).tags;
                    tags.remove(&old_simple_name);
                    tags.insert(new_name.simple_name.clone());
                }
                recipes.write(&db, &mut tx)?;
                remove(&db, &mut tx, LABELS, &label_doc_id(&old_simple_name))?;
            }

            label.name = new_name.name.clone();
            label.simple_name = new_name.simple_name.clone();
            put(
                &db,
                &mut tx,
                LABELS,
                &label_doc_id(&label.simple_name),
                &label,
            )?;
            Ok(label)
        })
    }

    /// Delete a label and remove it from every recipe.
    pub async fn delete_label(&self, label: &str) -> Result<()> {
        let simple_name = simplify(label);

        in_transaction!(self, |db, tx| {
            require(&db, &simple_name).await?;

            let mut recipes = Recipes::default();
            for id in recipes.containing(&db, "tags", &simple_name).await? {
                recipes.edit(&id).tags.remove(&simple_name);
            }
            recipes.write(&db, &mut tx)?;
            remove(&db, &mut tx, LABELS, &label_doc_id(&simple_name))?;
            Ok(())
        })
    }
}

async fn require(db: &FirestoreDb, simple_name: &str) -> Result<Label> {
    get(db, LABELS, &label_doc_id(simple_name))
        .await?
        .ok_or_else(|| StoreError::NotFound(format!("label {simple_name}")))
}

/// Change a label's recipe count by `delta`, creating it named `name` if it
/// does not exist and deleting it when no recipe uses it any more.
pub(super) async fn adjust_label(
    db: &FirestoreDb,
    tx: &mut Tx<'_>,
    simple_name: &str,
    name: Option<&str>,
    delta: i64,
) -> Result<()> {
    let doc_id = label_doc_id(simple_name);
    let mut label = match get::<Label>(db, LABELS, &doc_id).await? {
        Some(label) => label,
        None => Label {
            simple_name: simple_name.into(),
            name: name.unwrap_or(simple_name).into(),
            recipe_count: 0,
        },
    };

    let count = (i64::from(label.recipe_count) + delta).max(0);
    if count == 0 {
        remove(db, tx, LABELS, &doc_id)
    } else {
        label.recipe_count = u32::try_from(count).unwrap_or(u32::MAX);
        put(db, tx, LABELS, &doc_id, &label)
    }
}
