use super::loader::Recipes;
use super::{
    LABELS, RECIPES, Result, Store, StoreError, StoredRecipe, containing, get, in_transaction,
    label_doc_id, put, remove, with_prefix,
};
use firestore::{FirestoreDb, FirestoreTransaction};
use knife_core::input::LabelPatch;
use knife_core::{Label, LabelDetails, simplify};

impl Store {
    pub async fn list_labels(&self, prefix: &str) -> Result<Vec<Label>> {
        with_prefix(&self.db, LABELS, prefix).await
    }

    pub async fn get_label(&self, label: &str) -> Result<LabelDetails> {
        let label = require(&self.db, &simplify(label)).await?;
        let tagged: Vec<StoredRecipe> =
            containing(&self.db, RECIPES, "tags", &label.simple_name).await?;

        Ok(LabelDetails {
            label,
            recipes: tagged.iter().map(|s| s.recipe.summary()).collect(),
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
    tx: &mut FirestoreTransaction<'_>,
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
