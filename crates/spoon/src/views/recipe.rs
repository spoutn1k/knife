//! A recipe's page, for reading. Changes are made on its edit page.
//!
//! The recipes it uses come first, ingredients and directions, each under a
//! "For <recipe>" heading, in the order to prepare them.

use crate::api::{Api, use_api};
use crate::components::{Diets, ErrorBanner, Loading, Markdown, PenIcon};
use crate::{Error, LabelSet, Route};
use dioxus::prelude::*;
use knife_core::{IngredientId, Recipe, RecipeId, Requirement, simplify};
use std::collections::{BTreeMap, HashMap, HashSet};

#[component]
pub fn RecipePage(id: String) -> Element {
    let api = use_api();
    let loaded = use_resource(use_reactive!(|id| {
        let api = api.clone();
        async move {
            let recipe = api.recipe(&RecipeId(id)).await?;
            let requisites = requisites(&api, &recipe).await?;
            Ok::<_, Error>((recipe, requisites))
        }
    }));

    match &*loaded.read() {
        None => rsx! { Loading {} },
        Some(Err(e)) => rsx! { ErrorBanner { message: e.to_string() } },
        Some(Ok((recipe, requisites))) => rsx! {
            RecipeView { recipe: recipe.clone(), requisites: requisites.clone() }
        },
    }
}

/// Every recipe `recipe` uses, directly or through another, each before the
/// recipes using it: the order to prepare them in. Siblings are sorted by
/// name, and a recipe used twice appears once.
async fn requisites(api: &Api, recipe: &Recipe) -> Result<Vec<Recipe>, Error> {
    let mut loaded: HashMap<RecipeId, Recipe> = HashMap::new();
    let mut queue: Vec<RecipeId> = recipe.dependencies.keys().cloned().collect();
    while let Some(id) = queue.pop() {
        if loaded.contains_key(&id) {
            continue;
        }
        let requisite = api.recipe(&id).await?;
        queue.extend(requisite.dependencies.keys().cloned());
        loaded.insert(id, requisite);
    }

    // Depth-first, children before parents. The server keeps the graph
    // acyclic, so `done` is only needed for recipes used twice.
    fn visit(
        id: &RecipeId,
        loaded: &HashMap<RecipeId, Recipe>,
        done: &mut HashSet<RecipeId>,
        order: &mut Vec<Recipe>,
    ) {
        let Some(recipe) = loaded.get(id) else { return };
        if !done.insert(id.clone()) {
            return;
        }
        for child in sorted_dependencies(recipe) {
            visit(child, loaded, done, order);
        }
        order.push(recipe.clone());
    }
    let mut order = Vec::new();
    let mut done = HashSet::new();
    for id in sorted_dependencies(recipe) {
        visit(id, &loaded, &mut done, &mut order);
    }
    Ok(order)
}

fn sorted_dependencies(recipe: &Recipe) -> Vec<&RecipeId> {
    let mut ids: Vec<_> = recipe.dependencies.iter().collect();
    ids.sort_by_key(|(_, d)| simplify(&d.name));
    ids.into_iter().map(|(id, _)| id).collect()
}

#[component]
fn RecipeView(recipe: Recipe, requisites: Vec<Recipe>) -> Element {
    let labels = use_label_names();
    let with_ingredients: Vec<&Recipe> = requisites
        .iter()
        .filter(|r| !r.requirements.is_empty())
        .collect();
    let with_directions: Vec<&Recipe> = requisites
        .iter()
        .filter(|r| !r.directions.is_empty())
        .collect();
    let no_ingredients = with_ingredients.is_empty() && recipe.requirements.is_empty();
    let no_directions = with_directions.is_empty() && recipe.directions.is_empty();
    // The recipe's own sections are headed too when others come before them.
    let head_ingredients = !with_ingredients.is_empty() && !recipe.requirements.is_empty();
    let head_directions = !with_directions.is_empty();

    rsx! {
        article { class: "recipe",
            header { class: "recipe-header",
                if !recipe.tags.is_empty() {
                    ul { class: "tags eyebrow",
                        for tag in recipe.tags.iter() {
                            li { key: "{tag}", class: "tag plain",
                                Link { to: Route::RecipeList { labels: LabelSet::one(tag) },
                                    {labels.get(tag).unwrap_or(tag).clone()}
                                }
                            }
                        }
                    }
                }
                div { class: "name",
                    h1 { "{recipe.name}" }
                    Link {
                        class: "button secondary edit",
                        to: Route::EditRecipe { id: recipe.id.0.clone() },
                        title: "Edit",
                        "aria-label": "Edit",
                        PenIcon {}
                        span { "Edit" }
                    }
                }
                div { class: "byline",
                    if !recipe.author.is_empty() {
                        span { class: "muted", "From {recipe.author}" }
                    }
                    Diets { classification: recipe.classification }
                }
            }

            div { class: "columns",
                section {
                    h2 { "Ingredients" }
                    if no_ingredients {
                        p { class: "muted", "No ingredients yet." }
                    }
                    for requisite in with_ingredients {
                        div { key: "{requisite.id}",
                            ForHeading { recipe: recipe.clone(), requisite: requisite.clone() }
                            Ingredients { recipe: requisite.clone() }
                        }
                    }
                    if head_ingredients {
                        h3 { "For {recipe.name}" }
                    }
                    Ingredients { recipe: recipe.clone() }
                }
                section {
                    h2 { "Directions" }
                    if no_directions {
                        p { class: "muted", "No directions yet." }
                    }
                    for requisite in with_directions {
                        div { key: "{requisite.id}",
                            ForHeading { recipe: recipe.clone(), requisite: requisite.clone() }
                            Markdown { text: requisite.directions.clone() }
                        }
                    }
                    if !recipe.directions.is_empty() {
                        if head_directions {
                            h3 { "For {recipe.name}" }
                        }
                        Markdown { text: recipe.directions.clone() }
                    }
                    if !recipe.information.is_empty() {
                        h2 { "Notes" }
                        Markdown { text: recipe.information.clone() }
                    }
                }
            }
        }
    }
}

/// "For <requisite>", linking to it. A recipe `recipe` uses directly also
/// shows how much of it, and whether it is optional.
#[component]
fn ForHeading(recipe: Recipe, requisite: Recipe) -> Element {
    let usage = recipe.dependencies.get(&requisite.id).map(|d| {
        let mut parts = Vec::new();
        if !d.quantity.is_empty() {
            parts.push(d.quantity.clone());
        }
        if d.optional {
            parts.push("optional".to_owned());
        }
        parts.join(", ")
    });

    rsx! {
        h3 {
            "For "
            Link { to: Route::RecipePage { id: requisite.id.0.clone() }, "{requisite.name}" }
            if let Some(usage) = usage.filter(|u| !u.is_empty()) {
                span { class: "muted", " ({usage})" }
            }
        }
    }
}

/// A recipe's own ingredients, by group.
#[component]
fn Ingredients(recipe: Recipe) -> Element {
    rsx! {
        for (group, list) in by_group(&recipe) {
            div { key: "{group}",
                if !group.is_empty() {
                    h4 { "{group}" }
                }
                ul { class: "requirements",
                    for (ingredient, requirement) in list {
                        li { key: "{ingredient}",
                            span { class: "quantity", "{requirement.quantity}" }
                            span { class: "name",
                                Link { to: Route::IngredientPage { id: ingredient.0.clone() }, "{requirement.name}" }
                                if requirement.optional {
                                    span { class: "muted", " (optional)" }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

/// A recipe's requirements by group, ungrouped first, each sorted by
/// ingredient name.
pub(super) fn by_group(recipe: &Recipe) -> BTreeMap<&str, Vec<(&IngredientId, &Requirement)>> {
    let mut groups: BTreeMap<&str, Vec<_>> = BTreeMap::new();
    for (id, requirement) in &recipe.requirements {
        groups
            .entry(requirement.group.as_str())
            .or_default()
            .push((id, requirement));
    }
    for list in groups.values_mut() {
        list.sort_by_key(|(_, r)| simplify(&r.name));
    }
    groups
}

/// Display names of the labels, by simple name. Recipes store only the
/// simple names of their tags.
pub(super) fn use_label_names() -> HashMap<String, String> {
    let api = use_api();
    let labels = use_resource(move || {
        let api = api.clone();
        async move { api.labels("").await }
    });
    match &*labels.read() {
        Some(Ok(labels)) => labels
            .iter()
            .map(|l| (l.simple_name.clone(), l.name.clone()))
            .collect(),
        _ => HashMap::new(),
    }
}
