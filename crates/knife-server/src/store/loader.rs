//! Recipes read during a transaction, kept in memory so later reads see
//! earlier changes, and written back together at the end.

use super::{RECIPES, Result, StoreError, StoredRecipe, Tx, containing, get, put_recipe};
use firestore::FirestoreDb;
use knife_core::graph::{Graph, Node};
use knife_core::{Recipe, RecipeId};
use std::collections::{BTreeMap, BTreeSet, VecDeque};

#[derive(Default)]
pub(super) struct Recipes {
    loaded: BTreeMap<RecipeId, Recipe>,
    dirty: BTreeSet<RecipeId>,
}

impl Recipes {
    /// Load a recipe, or fail with 404.
    pub async fn require(&mut self, db: &FirestoreDb, id: &RecipeId) -> Result<&Recipe> {
        self.fetch(db, id).await?;
        self.loaded
            .get(id)
            .ok_or_else(|| StoreError::NotFound(format!("recipe {id}")))
    }

    /// Get a loaded recipe to modify; it will be written back.
    pub fn edit(&mut self, id: &RecipeId) -> &mut Recipe {
        self.dirty.insert(id.clone());
        self.loaded.get_mut(id).expect("recipe loaded before edit")
    }

    async fn fetch(&mut self, db: &FirestoreDb, id: &RecipeId) -> Result<()> {
        if !self.loaded.contains_key(id) {
            let stored: Option<StoredRecipe> = get(db, RECIPES, &id.0).await?;
            if let Some(stored) = stored {
                self.loaded.insert(id.clone(), stored.recipe);
            }
        }
        Ok(())
    }

    /// Recipes that depend directly on `id`, as stored before this
    /// transaction.
    pub async fn dependants(&mut self, db: &FirestoreDb, id: &RecipeId) -> Result<Vec<RecipeId>> {
        self.containing(db, "requisite_ids", &id.0).await
    }

    /// Recipes whose array `field` contains `value`.
    pub async fn containing(
        &mut self,
        db: &FirestoreDb,
        field: &str,
        value: &str,
    ) -> Result<Vec<RecipeId>> {
        let found: Vec<StoredRecipe> = containing(db, RECIPES, field, value).await?;
        Ok(found
            .into_iter()
            .map(|stored| {
                let id = stored.recipe.id.clone();
                self.loaded.entry(id.clone()).or_insert(stored.recipe);
                id
            })
            .collect())
    }

    /// Check that `recipe` may depend on `requisite`, loading every recipe
    /// `requisite` depends on.
    pub async fn check_new_dependency(
        &mut self,
        db: &FirestoreDb,
        recipe: &RecipeId,
        requisite: &RecipeId,
    ) -> Result<()> {
        let mut queue = VecDeque::from([requisite.clone()]);
        let mut seen = BTreeSet::new();
        while let Some(id) = queue.pop_front() {
            if !seen.insert(id.clone()) {
                continue;
            }
            self.fetch(db, &id).await?;
            if let Some(found) = self.loaded.get(&id) {
                queue.extend(found.dependencies.keys().cloned());
            }
        }

        self.graph().check_new_dependency(recipe, requisite)?;
        Ok(())
    }

    /// Recompute classifications after `changed` recipes' requirements or
    /// dependencies changed in memory, loading every recipe that depends on
    /// them and every requisite of those.
    pub async fn propagate(&mut self, db: &FirestoreDb, changed: &[RecipeId]) -> Result<()> {
        let mut affected = BTreeSet::new();
        let mut queue: VecDeque<RecipeId> = changed.iter().cloned().collect();
        while let Some(id) = queue.pop_front() {
            if affected.insert(id.clone()) {
                queue.extend(self.dependants(db, &id).await?);
            }
        }

        let requisites: BTreeSet<RecipeId> = affected
            .iter()
            .filter_map(|id| self.loaded.get(id))
            .flat_map(|r| r.dependencies.keys().cloned())
            .collect();
        for id in &requisites {
            self.fetch(db, id).await?;
        }

        for (id, classification) in self.graph().propagate(changed)? {
            self.edit(&id).classification = classification;
        }
        Ok(())
    }

    fn graph(&self) -> Graph {
        let mut graph = Graph::new();
        for (id, recipe) in &self.loaded {
            graph.insert(id.clone(), Node::from(recipe));
        }
        graph
    }

    /// Queue every edited recipe for writing.
    pub fn write(&self, db: &FirestoreDb, tx: &mut Tx) -> Result<()> {
        for id in &self.dirty {
            put_recipe(db, tx, &self.loaded[id])?;
        }
        Ok(())
    }
}
