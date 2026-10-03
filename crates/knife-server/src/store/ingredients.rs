use super::loader::Recipes;
use super::{
    INGREDIENTS, NAMES, NameDoc, NameKind, RECIPES, Result, Store, StoreError, StoredRecipe,
    containing, get, in_transaction, move_name, name_doc_id, name_taken_by, new_id, put, remove,
    with_prefix,
};
use firestore::FirestoreDb;
use knife_core::input::{IngredientPatch, NewIngredient};
use knife_core::{Ingredient, IngredientId, RecipeId, Summary};
use serde::Serialize;

/// An ingredient and the recipes that use it.
#[derive(Debug, Serialize)]
pub struct IngredientDetails {
    #[serde(flatten)]
    pub ingredient: Ingredient,
    pub used_in: Vec<Summary<RecipeId>>,
}

impl Store {
    pub async fn list_ingredients(&self, prefix: &str) -> Result<Vec<Summary<IngredientId>>> {
        let found: Vec<Ingredient> = with_prefix(&self.db, INGREDIENTS, prefix).await?;
        Ok(found.iter().map(Ingredient::summary).collect())
    }

    pub async fn get_ingredient(&self, id: &IngredientId) -> Result<IngredientDetails> {
        let ingredient = require(&self.db, id).await?;
        let used_in: Vec<StoredRecipe> =
            containing(&self.db, RECIPES, "ingredient_ids", &id.0).await?;

        Ok(IngredientDetails {
            ingredient,
            used_in: used_in.iter().map(|s| s.recipe.summary()).collect(),
        })
    }

    pub async fn create_ingredient(&self, input: &NewIngredient) -> Result<Ingredient> {
        let name = input.validate()?;
        let ingredient = Ingredient {
            id: IngredientId(new_id()),
            name: name.name,
            simple_name: name.simple_name,
            classification: input.classification(),
        };

        in_transaction!(self, |db, tx| {
            if let Some(holder) =
                name_taken_by(&db, NameKind::Ingredient, &ingredient.simple_name, None).await?
            {
                return Err(name_conflict(&db, &holder).await);
            }

            put(&db, &mut tx, INGREDIENTS, &ingredient.id.0, &ingredient)?;
            put(
                &db,
                &mut tx,
                NAMES,
                &name_doc_id(NameKind::Ingredient, &ingredient.simple_name),
                &NameDoc {
                    id: ingredient.id.0.clone(),
                },
            )?;
            Ok(ingredient.clone())
        })
    }

    /// Rename or reclassify an ingredient, updating the copies held by the
    /// recipes that use it and their classifications.
    pub async fn update_ingredient(
        &self,
        id: &IngredientId,
        patch: &IngredientPatch,
    ) -> Result<Ingredient> {
        let new_name = patch.validate()?;

        in_transaction!(self, |db, tx| {
            let mut ingredient = require(&db, id).await?;
            let old_simple_name = ingredient.simple_name.clone();

            if let Some(name) = &new_name {
                if let Some(holder) =
                    name_taken_by(&db, NameKind::Ingredient, &name.simple_name, Some(&id.0)).await?
                {
                    return Err(name_conflict(&db, &holder).await);
                }
                ingredient.name = name.name.clone();
                ingredient.simple_name = name.simple_name.clone();
            }
            let reclassified = patch.apply(ingredient.classification) != ingredient.classification;
            ingredient.classification = patch.apply(ingredient.classification);

            let mut recipes = Recipes::default();
            let users = recipes.containing(&db, "ingredient_ids", &id.0).await?;
            for recipe in &users {
                let requirement = recipes
                    .edit(recipe)
                    .requirements
                    .get_mut(id)
                    .expect("recipe found by ingredient_ids has the requirement");
                requirement.name = ingredient.name.clone();
                requirement.classification = ingredient.classification;
            }
            if reclassified {
                recipes.propagate(&db, &users).await?;
            }

            move_name(
                &db,
                &mut tx,
                NameKind::Ingredient,
                &old_simple_name,
                &ingredient.simple_name,
                &id.0,
            )?;
            put(&db, &mut tx, INGREDIENTS, &id.0, &ingredient)?;
            recipes.write(&db, &mut tx)?;
            Ok(ingredient)
        })
    }

    /// Delete an ingredient no recipe uses.
    pub async fn delete_ingredient(&self, id: &IngredientId) -> Result<()> {
        in_transaction!(self, |db, tx| {
            let ingredient = require(&db, id).await?;

            let users: Vec<StoredRecipe> =
                containing(&db, RECIPES, "ingredient_ids", &id.0).await?;
            if !users.is_empty() {
                return Err(StoreError::Conflict {
                    detail: format!("ingredient is used by {} recipe(s)", users.len()),
                    existing: Some(serde_json::json!(
                        users.iter().map(|s| s.recipe.summary()).collect::<Vec<_>>()
                    )),
                });
            }

            remove(&db, &mut tx, INGREDIENTS, &id.0)?;
            remove(
                &db,
                &mut tx,
                NAMES,
                &name_doc_id(NameKind::Ingredient, &ingredient.simple_name),
            )?;
            Ok(())
        })
    }
}

pub(super) async fn require(db: &FirestoreDb, id: &IngredientId) -> Result<Ingredient> {
    get(db, INGREDIENTS, &id.0)
        .await?
        .ok_or_else(|| StoreError::NotFound(format!("ingredient {id}")))
}

/// A 409 naming the ingredient that holds a name.
async fn name_conflict(db: &FirestoreDb, holder: &str) -> StoreError {
    let existing = get::<Ingredient>(db, INGREDIENTS, holder)
        .await
        .ok()
        .flatten()
        .map(|i| serde_json::json!(i.summary()));
    StoreError::Conflict {
        detail: "an ingredient with this name already exists".into(),
        existing,
    }
}
