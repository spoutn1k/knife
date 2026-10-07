//! Domain types and rules for knife, a shared family recipe book.
//!
//! This crate does no I/O, so the server and a future wasm frontend can share
//! it: everything here is validation, naming and graph logic over data the
//! caller has already loaded.

mod classification;
mod error;
pub mod graph;
pub mod input;
mod model;
mod names;

pub use classification::Classification;
pub use error::Error;
pub use model::{
    Dependency, Ingredient, IngredientDetails, IngredientId, Label, LabelDetails, MemberListing,
    Recipe, RecipeDetails, RecipeId, RecipeListing, Requirement, Summary, UserId,
};
pub use names::{MAX_NAME_LEN, ValidName, prefix_bounds, simplify};
