//! The v0.3 export: every recipe and ingredient as the old API returned
//! them. Its `labels` list is not needed, since recipes name their tags.

use knife_core::Classification;
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct Export {
    pub recipes: Vec<Recipe>,
    pub ingredients: Vec<Ingredient>,
}

/// An id and name pointing at another record of the export.
#[derive(Debug, Deserialize)]
pub struct Ref {
    pub id: String,
    pub name: String,
}

#[derive(Debug, Deserialize)]
pub struct Ingredient {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub classifications: Classification,
}

#[derive(Debug, Deserialize)]
pub struct Recipe {
    pub id: String,
    pub name: String,
    #[serde(default)]
    pub author: String,
    #[serde(default)]
    pub directions: String,
    #[serde(default)]
    pub information: String,
    /// As v0.3 computed it; compared with the server's after the import.
    #[serde(default)]
    pub classifications: Classification,
    #[serde(default)]
    pub requirements: Vec<Requirement>,
    #[serde(default)]
    pub dependencies: Vec<Dependency>,
    #[serde(default)]
    pub tags: Vec<Ref>,
}

#[derive(Debug, Deserialize)]
pub struct Requirement {
    pub ingredient: Ref,
    pub quantity: String,
    #[serde(default)]
    pub optional: bool,
    #[serde(default)]
    pub group: String,
}

#[derive(Debug, Deserialize)]
pub struct Dependency {
    pub recipe: Ref,
    #[serde(default)]
    pub quantity: String,
    #[serde(default)]
    pub optional: bool,
}
