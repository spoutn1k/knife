//! One module per kind of page.

mod edit_recipe;
mod ingredients;
mod label_graph;
mod labels;
mod recipe;
mod recipes;
mod sign_in;

pub use edit_recipe::EditRecipe;
pub use ingredients::{IngredientList, IngredientPage};
pub use label_graph::LabelGraph;
pub use labels::LabelList;
pub use recipe::RecipePage;
pub use recipes::{NewRecipe, RecipeList};
pub use sign_in::SignIn;

use crate::{LabelSet, Route};
use dioxus::prelude::*;

#[component]
pub fn NotFound(segments: Vec<String>) -> Element {
    rsx! {
        h1 { "Not found" }
        p { "There is no page at /{segments.join(\"/\")}." }
        Link { to: Route::RecipeList { labels: LabelSet::default() }, "Back to the recipes" }
    }
}
