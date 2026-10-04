//! The export format, and `chopstick export`, which downloads it.
//!
//! Each fact is stored once. The server keeps copies for speed (an
//! ingredient's name and flags in every recipe using it, a recipe's own
//! classification, a label's recipe count); they are left out here, since
//! the server rebuilds them on import. Records point at each other by id,
//! and recipes at labels by simple name.

use crate::Error;
use crate::client::Client;
use knife_core::input::{DependencyInput, RequirementInput};
use knife_core::{
    Classification, IngredientDetails, IngredientId, Label, RecipeDetails, RecipeId, RecipeListing,
    Summary, UserId,
};
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

/// Bumped when a field changes meaning or goes away.
pub const VERSION: u32 = 2;

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Export {
    pub version: u32,
    pub ingredients: Vec<Ingredient>,
    /// Display names of the labels; recipes refer to them by simple name.
    pub labels: Vec<String>,
    pub recipes: Vec<Recipe>,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Ingredient {
    pub id: IngredientId,
    pub name: String,
    #[serde(default)]
    pub classification: Classification,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Recipe {
    pub id: RecipeId,
    pub name: String,
    #[serde(default)]
    pub author: String,
    #[serde(default)]
    pub directions: String,
    #[serde(default)]
    pub information: String,
    #[serde(default)]
    pub requirements: BTreeMap<IngredientId, RequirementInput>,
    #[serde(default)]
    pub dependencies: BTreeMap<RecipeId, DependencyInput>,
    /// Simple names of the labels on the recipe.
    #[serde(default)]
    pub tags: BTreeSet<String>,
    /// Kept for the record: an import credits whoever runs it instead.
    pub created_by: UserId,
    pub updated_by: UserId,
}

impl From<knife_core::Recipe> for Recipe {
    fn from(recipe: knife_core::Recipe) -> Self {
        Self {
            id: recipe.id,
            name: recipe.name,
            author: recipe.author,
            directions: recipe.directions,
            information: recipe.information,
            requirements: recipe
                .requirements
                .iter()
                .map(|(id, r)| (id.clone(), r.into()))
                .collect(),
            dependencies: recipe
                .dependencies
                .into_iter()
                .map(|(id, d)| {
                    let input = DependencyInput {
                        quantity: d.quantity,
                        optional: d.optional,
                    };
                    (id, input)
                })
                .collect(),
            tags: recipe.tags,
            created_by: recipe.created_by,
            updated_by: recipe.updated_by,
        }
    }
}

pub fn download(client: &Client) -> Result<Export, Error> {
    let summaries: Vec<Summary<IngredientId>> = get(client, &["ingredients"])?;
    eprintln!("Ingredients ({})", summaries.len());
    let ingredients = summaries
        .iter()
        .map(|s| {
            let details: IngredientDetails = get(client, &["ingredients", &s.id.0])?;
            let ingredient = details.ingredient;
            Ok(Ingredient {
                id: ingredient.id,
                name: ingredient.name,
                classification: ingredient.classification,
            })
        })
        .collect::<Result<_, Error>>()?;

    let labels: Vec<Label> = get(client, &["labels"])?;

    let listings: Vec<RecipeListing> = get(client, &["recipes"])?;
    let mut recipes = Vec::with_capacity(listings.len());
    for (n, listing) in listings.iter().enumerate() {
        eprintln!("[{}/{}] {}", n + 1, listings.len(), listing.name);
        let details: RecipeDetails = get(client, &["recipes", &listing.id.0])?;
        recipes.push(details.recipe.into());
    }

    Ok(Export {
        version: VERSION,
        ingredients,
        labels: labels.into_iter().map(|l| l.name).collect(),
        recipes,
    })
}

fn get<T: DeserializeOwned>(client: &Client, segments: &[&str]) -> Result<T, Error> {
    serde_json::from_value(client.get(segments, &[])?)
        .map_err(|e| Error::Response(format!("/api/{}", segments.join("/")), e))
}
