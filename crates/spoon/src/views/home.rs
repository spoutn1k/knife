//! The landing page.

use crate::{DietSet, LabelSet, Route};
use dioxus::prelude::*;

/// A placeholder while the landing page takes shape: the full recipe list
/// lives at `/recipes`.
#[component]
pub fn Home() -> Element {
    rsx! {
        div { class: "title-row",
            h1 { "Recipe book" }
            Link { class: "button", to: Route::NewRecipe {}, "New recipe" }
        }
        ul { class: "links",
            li { Link { to: Route::RecipeList { labels: LabelSet::default(), diets: DietSet::default() }, "All recipes" } }
            li { Link { to: Route::IngredientList {}, "Ingredients" } }
            li { Link { to: Route::LabelList {}, "Labels" } }
        }
    }
}
