use crate::Classification;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;

macro_rules! id_type {
    ($(#[$meta:meta])* $name:ident) => {
        $(#[$meta])*
        #[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
        #[serde(transparent)]
        pub struct $name(pub String);

        impl fmt::Display for $name {
            fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
                self.0.fmt(f)
            }
        }

        impl From<&str> for $name {
            fn from(id: &str) -> Self {
                Self(id.to_owned())
            }
        }
    };
}

id_type!(RecipeId);
id_type!(IngredientId);
id_type!(
    /// Firebase Auth uid.
    UserId
);

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Ingredient {
    pub id: IngredientId,
    pub name: String,
    pub simple_name: String,
    pub classification: Classification,
}

/// A recipe with its requirements, dependencies and tags embedded, as stored
/// in a single Firestore document.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Recipe {
    pub id: RecipeId,
    pub name: String,
    pub simple_name: String,
    /// Where the recipe comes from ("Grandma", a book), as free text.
    #[serde(default)]
    pub author: String,
    #[serde(default)]
    pub directions: String,
    #[serde(default)]
    pub information: String,
    #[serde(default)]
    pub requirements: BTreeMap<IngredientId, Requirement>,
    #[serde(default)]
    pub dependencies: BTreeMap<RecipeId, Dependency>,
    /// Simple names of the labels on this recipe.
    #[serde(default)]
    pub tags: BTreeSet<String>,
    /// Stored on write; see [`crate::graph`].
    #[serde(default)]
    pub classification: Classification,
    /// The family member who added the recipe.
    pub created_by: UserId,
    pub updated_by: UserId,
}

/// An ingredient used by a recipe. `name` and `classification` are copies of
/// the ingredient's, kept in sync when it changes, so a recipe's own flags can
/// be computed without reading its ingredients.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Requirement {
    pub name: String,
    #[serde(default)]
    pub classification: Classification,
    pub quantity: String,
    #[serde(default)]
    pub optional: bool,
    #[serde(default)]
    pub group: String,
}

impl Recipe {
    /// Union of this recipe's own ingredients' flags, ignoring dependencies.
    pub fn own_classification(&self) -> Classification {
        self.requirements
            .values()
            .map(|r| r.classification)
            .collect()
    }

    pub fn summary(&self) -> Summary<RecipeId> {
        Summary {
            id: self.id.clone(),
            name: self.name.clone(),
        }
    }

    pub fn listing(&self) -> RecipeListing {
        RecipeListing {
            id: self.id.clone(),
            name: self.name.clone(),
            author: self.author.clone(),
            tags: self.tags.clone(),
            classification: self.classification,
            requirement_count: self.requirements.len() as u32,
            dependency_count: self.dependencies.len() as u32,
        }
    }
}

/// A recipe as `GET /recipes` lists it: enough for a table of recipes,
/// without the ingredients and directions.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RecipeListing {
    pub id: RecipeId,
    pub name: String,
    pub author: String,
    /// Simple names of the labels on the recipe.
    pub tags: BTreeSet<String>,
    pub classification: Classification,
    /// How many different ingredients the recipe needs, optional ones
    /// included. `GET /recipes` counts those of the recipes it uses too;
    /// [`Recipe::listing`], only the recipe's own.
    #[serde(default)]
    pub requirement_count: u32,
    /// How many other recipes the recipe uses directly.
    #[serde(default)]
    pub dependency_count: u32,
}

impl Ingredient {
    pub fn summary(&self) -> Summary<IngredientId> {
        Summary {
            id: self.id.clone(),
            name: self.name.clone(),
        }
    }
}

/// An id and display name, as returned by list endpoints.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Summary<Id> {
    pub id: Id,
    pub name: String,
}

/// Another recipe used by a recipe. `name` is a copy of the requisite's name,
/// kept in sync on rename.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Dependency {
    pub name: String,
    #[serde(default)]
    pub quantity: String,
    #[serde(default)]
    pub optional: bool,
}

/// A label, identified by its simple name.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Label {
    pub simple_name: String,
    pub name: String,
    pub recipe_count: u32,
}

/// An ingredient and the recipes that use it, as `GET /ingredients/{id}`
/// returns it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct IngredientDetails {
    #[serde(flatten)]
    pub ingredient: Ingredient,
    pub used_in: Vec<Summary<RecipeId>>,
}

/// A recipe and the recipes that use it directly, sorted by name, as
/// `GET /recipes/{id}` returns it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RecipeDetails {
    #[serde(flatten)]
    pub recipe: Recipe,
    pub used_in: Vec<Summary<RecipeId>>,
}

/// A label and the recipes tagged with it, as `GET /labels/{name}` returns it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct LabelDetails {
    #[serde(flatten)]
    pub label: Label,
    pub recipes: Vec<Summary<RecipeId>>,
}
