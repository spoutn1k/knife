use super::labels::adjust_label;
use super::loader::Recipes;
use super::{
    NAMES, NameDoc, NameKind, RECIPES, Result, Store, StoreError, StoredRecipe, get,
    in_transaction, ingredients, move_name, name_doc_id, name_taken_by, new_id, put, put_recipe,
    remove, with_prefix,
};
use firestore::FirestoreDb;
use knife_core::input::{DependencyInput, NewRecipe, RecipePatch, RequirementInput};
use knife_core::{
    Classification, Dependency, IngredientId, Recipe, RecipeId, Requirement, Summary, UserId,
    ValidName, simplify,
};
use std::collections::{BTreeMap, BTreeSet};

impl Store {
    pub async fn list_recipes(&self, prefix: &str) -> Result<Vec<Summary<RecipeId>>> {
        let found: Vec<StoredRecipe> = with_prefix(&self.db, RECIPES, prefix).await?;
        Ok(found.iter().map(|s| s.recipe.summary()).collect())
    }

    pub async fn get_recipe(&self, id: &RecipeId) -> Result<Recipe> {
        let stored: Option<StoredRecipe> = get(&self.db, RECIPES, &id.0).await?;
        stored
            .map(|s| s.recipe)
            .ok_or_else(|| StoreError::NotFound(format!("recipe {id}")))
    }

    pub async fn create_recipe(&self, input: &NewRecipe, user: &UserId) -> Result<Recipe> {
        let name = input.validate()?;
        let recipe = Recipe {
            id: RecipeId(new_id()),
            name: name.name,
            simple_name: name.simple_name,
            author: input.author.trim().to_owned(),
            directions: input.directions.clone(),
            information: input.information.clone(),
            requirements: BTreeMap::new(),
            dependencies: BTreeMap::new(),
            tags: BTreeSet::new(),
            classification: Classification::default(),
            created_by: user.clone(),
            updated_by: user.clone(),
        };

        in_transaction!(self, |db, tx| {
            if let Some(holder) =
                name_taken_by(&db, NameKind::Recipe, &recipe.simple_name, None).await?
            {
                return Err(name_conflict(&db, &holder).await);
            }

            put_recipe(&db, &mut tx, &recipe)?;
            put(
                &db,
                &mut tx,
                NAMES,
                &name_doc_id(NameKind::Recipe, &recipe.simple_name),
                &NameDoc {
                    id: recipe.id.0.clone(),
                },
            )?;
            Ok(recipe.clone())
        })
    }

    /// Edit a recipe's own fields. A rename updates the copies of the name
    /// held by recipes that depend on it.
    pub async fn update_recipe(
        &self,
        id: &RecipeId,
        patch: &RecipePatch,
        user: &UserId,
    ) -> Result<Recipe> {
        let new_name = patch.validate()?;

        in_transaction!(self, |db, tx| {
            let mut recipes = Recipes::default();
            let old_simple_name = recipes.require(&db, id).await?.simple_name.clone();

            if let Some(name) = &new_name {
                if let Some(holder) =
                    name_taken_by(&db, NameKind::Recipe, &name.simple_name, Some(&id.0)).await?
                {
                    return Err(name_conflict(&db, &holder).await);
                }
                for dependant in recipes.dependants(&db, id).await? {
                    if let Some(dependency) = recipes.edit(&dependant).dependencies.get_mut(id) {
                        dependency.name = name.name.clone();
                    }
                }
            }

            let recipe = recipes.edit(id);
            if let Some(name) = &new_name {
                recipe.name = name.name.clone();
                recipe.simple_name = name.simple_name.clone();
            }
            if let Some(author) = &patch.author {
                recipe.author = author.trim().to_owned();
            }
            if let Some(directions) = &patch.directions {
                recipe.directions = directions.clone();
            }
            if let Some(information) = &patch.information {
                recipe.information = information.clone();
            }
            recipe.updated_by = user.clone();
            let recipe = recipe.clone();

            move_name(
                &db,
                &mut tx,
                NameKind::Recipe,
                &old_simple_name,
                &recipe.simple_name,
                &id.0,
            )?;
            recipes.write(&db, &mut tx)?;
            Ok(recipe)
        })
    }

    /// Delete a recipe no other recipe depends on.
    pub async fn delete_recipe(&self, id: &RecipeId) -> Result<()> {
        in_transaction!(self, |db, tx| {
            let mut recipes = Recipes::default();
            let recipe = recipes.require(&db, id).await?.clone();

            let dependants = recipes.dependants(&db, id).await?;
            if !dependants.is_empty() {
                let mut users = Vec::new();
                for dependant in &dependants {
                    users.push(recipes.require(&db, dependant).await?.summary());
                }
                return Err(StoreError::Conflict {
                    detail: format!("recipe is used by {} other recipe(s)", users.len()),
                    existing: Some(serde_json::json!(users)),
                });
            }

            for tag in &recipe.tags {
                adjust_label(&db, &mut tx, tag, None, -1).await?;
            }
            remove(&db, &mut tx, RECIPES, &id.0)?;
            remove(
                &db,
                &mut tx,
                NAMES,
                &name_doc_id(NameKind::Recipe, &recipe.simple_name),
            )?;
            Ok(())
        })
    }

    /// Add or replace the requirement of `ingredient` by a recipe.
    pub async fn put_requirement(
        &self,
        id: &RecipeId,
        ingredient: &IngredientId,
        input: &RequirementInput,
        user: &UserId,
    ) -> Result<Recipe> {
        input.validate()?;

        in_transaction!(self, |db, tx| {
            let mut recipes = Recipes::default();
            recipes.require(&db, id).await?;
            let found = ingredients::require(&db, ingredient).await?;

            let recipe = recipes.edit(id);
            recipe.requirements.insert(
                ingredient.clone(),
                Requirement {
                    name: found.name,
                    classification: found.classification,
                    quantity: input.quantity.clone(),
                    optional: input.optional,
                    group: input.group.clone(),
                },
            );
            recipe.updated_by = user.clone();

            finish(&db, &mut tx, &mut recipes, id).await
        })
    }

    pub async fn delete_requirement(
        &self,
        id: &RecipeId,
        ingredient: &IngredientId,
        user: &UserId,
    ) -> Result<Recipe> {
        in_transaction!(self, |db, tx| {
            let mut recipes = Recipes::default();
            if !recipes
                .require(&db, id)
                .await?
                .requirements
                .contains_key(ingredient)
            {
                return Err(StoreError::NotFound(format!(
                    "requirement of ingredient {ingredient}"
                )));
            }

            let recipe = recipes.edit(id);
            recipe.requirements.remove(ingredient);
            recipe.updated_by = user.clone();

            finish(&db, &mut tx, &mut recipes, id).await
        })
    }

    /// Add or replace the dependency of a recipe on `requisite`.
    pub async fn put_dependency(
        &self,
        id: &RecipeId,
        requisite: &RecipeId,
        input: &DependencyInput,
        user: &UserId,
    ) -> Result<Recipe> {
        in_transaction!(self, |db, tx| {
            let mut recipes = Recipes::default();
            recipes.require(&db, id).await?;
            let requisite_name = recipes.require(&db, requisite).await?.name.clone();
            recipes.check_new_dependency(&db, id, requisite).await?;

            let recipe = recipes.edit(id);
            recipe.dependencies.insert(
                requisite.clone(),
                Dependency {
                    name: requisite_name,
                    quantity: input.quantity.clone(),
                    optional: input.optional,
                },
            );
            recipe.updated_by = user.clone();

            finish(&db, &mut tx, &mut recipes, id).await
        })
    }

    pub async fn delete_dependency(
        &self,
        id: &RecipeId,
        requisite: &RecipeId,
        user: &UserId,
    ) -> Result<Recipe> {
        in_transaction!(self, |db, tx| {
            let mut recipes = Recipes::default();
            if !recipes
                .require(&db, id)
                .await?
                .dependencies
                .contains_key(requisite)
            {
                return Err(StoreError::NotFound(format!(
                    "dependency on recipe {requisite}"
                )));
            }

            let recipe = recipes.edit(id);
            recipe.dependencies.remove(requisite);
            recipe.updated_by = user.clone();

            finish(&db, &mut tx, &mut recipes, id).await
        })
    }

    /// Tag a recipe with a label, creating the label if needed. Tagging
    /// twice is a no-op.
    pub async fn put_tag(&self, id: &RecipeId, label: &str, user: &UserId) -> Result<Recipe> {
        let label = ValidName::label(label)?;

        in_transaction!(self, |db, tx| {
            let mut recipes = Recipes::default();
            let recipe = recipes.require(&db, id).await?;
            if recipe.tags.contains(&label.simple_name) {
                return Ok(recipe.clone());
            }

            adjust_label(&db, &mut tx, &label.simple_name, Some(&label.name), 1).await?;
            let recipe = recipes.edit(id);
            recipe.tags.insert(label.simple_name.clone());
            recipe.updated_by = user.clone();
            let recipe = recipe.clone();

            recipes.write(&db, &mut tx)?;
            Ok(recipe)
        })
    }

    pub async fn delete_tag(&self, id: &RecipeId, label: &str, user: &UserId) -> Result<Recipe> {
        let simple_name = simplify(label);

        in_transaction!(self, |db, tx| {
            let mut recipes = Recipes::default();
            if !recipes.require(&db, id).await?.tags.contains(&simple_name) {
                return Err(StoreError::NotFound(format!("tag {label}")));
            }

            adjust_label(&db, &mut tx, &simple_name, None, -1).await?;
            let recipe = recipes.edit(id);
            recipe.tags.remove(&simple_name);
            recipe.updated_by = user.clone();
            let recipe = recipe.clone();

            recipes.write(&db, &mut tx)?;
            Ok(recipe)
        })
    }
}

/// After a change to `id`'s requirements or dependencies: recompute
/// classifications, queue the writes and return the updated recipe.
async fn finish(
    db: &FirestoreDb,
    tx: &mut firestore::FirestoreTransaction<'_>,
    recipes: &mut Recipes,
    id: &RecipeId,
) -> Result<Recipe> {
    recipes.propagate(db, std::slice::from_ref(id)).await?;
    recipes.write(db, tx)?;
    Ok(recipes.require(db, id).await?.clone())
}

/// A 409 naming the recipe that holds a name.
async fn name_conflict(db: &FirestoreDb, holder: &str) -> StoreError {
    let existing = get::<StoredRecipe>(db, RECIPES, holder)
        .await
        .ok()
        .flatten()
        .map(|s| serde_json::json!(s.recipe.summary()));
    StoreError::Conflict {
        detail: "a recipe with this name already exists".into(),
        existing,
    }
}
