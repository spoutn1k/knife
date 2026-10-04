//! The recipe list, and the page to create a recipe.

use crate::api::use_api;
use crate::components::{
    DietIcons, ErrorBanner, Highlight, Loading, Match, SearchBox, fuzzy_filter,
};
use crate::views::edit_recipe::RecipeForm;
use crate::views::recipe::use_label_names;
use crate::{LabelSet, Route};
use dioxus::prelude::*;
use knife_core::{Label, RecipeId, RecipeListing, Summary, simplify};
use std::collections::HashMap;

/// Characters of label names shown per row before the rest become "+n".
const LABEL_BUDGET: usize = 24;

#[component]
pub fn RecipeList(labels: LabelSet) -> Element {
    let api = use_api();
    let search = use_signal(String::new);
    // Every recipe, loaded once and filtered here as the search is typed.
    let recipes = use_resource({
        let api = api.clone();
        move || {
            let api = api.clone();
            async move { api.recipes("").await }
        }
    });
    let all_labels = use_resource(move || {
        let api = api.clone();
        async move { api.labels("").await }
    });
    // Open when arriving with labels selected, as from a tag link.
    let mut open = use_signal(|| !labels.0.is_empty());

    // What is filtered, shown in the header so it is visible when closed.
    let mut active = Vec::new();
    if !search.read().trim().is_empty() {
        active.push(format!("“{}”", search.read().trim()));
    }
    for label in &labels.0 {
        let name = match &*all_labels.read() {
            Some(Ok(all)) => all
                .iter()
                .find(|l| &l.simple_name == label)
                .map(|l| l.name.clone()),
            _ => None,
        };
        active.push(name.unwrap_or_else(|| label.clone()));
    }

    rsx! {
        div { class: "title-row",
            h1 { "Recipes" }
            Link { class: "button", to: Route::NewRecipe {}, "New recipe" }
        }
        details { class: "filters", open: open(),
            summary {
                onclick: move |e| {
                    e.prevent_default();
                    open.toggle();
                },
                "Filter"
                if !active.is_empty() {
                    span { class: "muted", " · {active.join(\" · \")}" }
                }
            }
            SearchBox { value: search, placeholder: "Recipe name" }
            if let Some(Ok(all)) = &*all_labels.read() {
                LabelFilter { labels: all.clone(), selected: labels.clone() }
            }
        }
        match &*recipes.read() {
            None => rsx! { Loading {} },
            Some(Err(e)) => rsx! { ErrorBanner { message: e.to_string() } },
            Some(Ok(list)) => {
                let labelled: Vec<RecipeListing> = list
                    .iter()
                    .filter(|r| labels.0.is_subset(&r.tags))
                    .cloned()
                    .collect();
                let shown = fuzzy_filter(&labelled, |r| &r.name, &search.read());
                if shown.is_empty() {
                    rsx! {
                        p { class: "muted",
                            if list.is_empty() {
                                "No recipes yet."
                            } else {
                                "No recipe matches."
                            }
                        }
                    }
                } else {
                    rsx! { RecipeTable { recipes: shown } }
                }
            }
        }
    }
}

/// The labels to filter the list by. Selecting a label adds it to the page's
/// `?labels=`, selecting it again removes it, and "All" clears them.
#[component]
fn LabelFilter(labels: Vec<Label>, selected: LabelSet) -> Element {
    let mut labels: Vec<Label> = labels.into_iter().filter(|l| l.recipe_count > 0).collect();
    labels.sort_by_key(|l| l.simple_name.clone());
    if labels.is_empty() {
        return rsx! {};
    }

    rsx! {
        nav { class: "label-filter", "aria-label": "Filter by label",
            Link {
                class: if selected.0.is_empty() { "tag plain selected" } else { "tag plain" },
                to: Route::RecipeList { labels: LabelSet::default() },
                "All"
            }
            for label in labels {
                Link {
                    key: "{label.simple_name}",
                    class: if selected.0.contains(&label.simple_name) { "tag plain selected" } else { "tag plain" },
                    to: Route::RecipeList { labels: selected.toggled(&label.simple_name) },
                    "{label.name}"
                    span { class: "count", "{label.recipe_count}" }
                }
            }
        }
    }
}

#[component]
fn RecipeTable(recipes: Vec<Match<RecipeListing>>) -> Element {
    let labels = use_label_names();

    rsx! {
        table { class: "recipes",
            thead {
                tr {
                    th { "Recipe" }
                    th { "Diet" }
                    th { class: "labels", "Labels" }
                    th { class: "author", "From" }
                }
            }
            tbody {
                for Match { item: recipe, indices } in recipes {
                    tr { key: "{recipe.id}",
                        td {
                            Link { to: Route::RecipePage { id: recipe.id.0.clone() },
                                Highlight { text: recipe.name.clone(), indices }
                            }
                        }
                        td { DietIcons { classification: recipe.classification } }
                        td { class: "labels",
                            RecipeTags {
                                tags: recipe.tags.iter().cloned().collect(),
                                labels: labels.clone(),
                            }
                        }
                        td { class: "author muted", "{recipe.author}" }
                    }
                }
            }
        }
    }
}

/// A recipe's labels, as many as fit in [`LABEL_BUDGET`], then "+n" for the
/// rest, which hovering it lists.
#[component]
fn RecipeTags(tags: Vec<String>, labels: HashMap<String, String>) -> Element {
    let mut names: Vec<(String, String)> = tags
        .into_iter()
        .map(|tag| {
            let name = labels.get(&tag).cloned().unwrap_or_else(|| tag.clone());
            (tag, name)
        })
        .collect();
    names.sort_by_key(|(_, name)| simplify(name));

    // At least one label, then more while they fit.
    let mut used = 0;
    let shown = names
        .iter()
        .take_while(|(_, name)| {
            let fits = used == 0 || used + name.chars().count() <= LABEL_BUDGET;
            used += name.chars().count();
            fits
        })
        .count();
    let hidden: Vec<&str> = names[shown..].iter().map(|(_, n)| n.as_str()).collect();

    rsx! {
        span { class: "tags",
            for (tag, name) in names[..shown].iter() {
                Link { key: "{tag}", class: "tag plain", to: Route::RecipeList { labels: LabelSet::one(tag) }, "{name}" }
            }
            if !hidden.is_empty() {
                span { class: "more", title: hidden.join(", "), "+{hidden.len()}" }
            }
        }
    }
}

/// A list of links to recipes.
#[component]
pub fn RecipeLinks(recipes: Vec<Summary<RecipeId>>) -> Element {
    rsx! {
        ul { class: "links",
            for recipe in recipes {
                li { key: "{recipe.id}",
                    Link { to: Route::RecipePage { id: recipe.id.0.clone() }, "{recipe.name}" }
                }
            }
        }
    }
}

#[component]
pub fn NewRecipe() -> Element {
    rsx! {
        h1 { "New recipe" }
        p { class: "muted", "Ingredients and tags come next, once the recipe is created." }
        RecipeForm { recipe: None }
    }
}
