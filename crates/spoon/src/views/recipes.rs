//! The recipe list, and the dialog to create a recipe.

use crate::api::use_api;
use crate::components::{
    Diet, DietIcon, DietIcons, ErrorBanner, Highlight, Loading, Match, SearchBox, SortColumn,
    SortHeader, fuzzy_filter, sort_rows, tint, use_mutation,
};
use crate::views::edit_recipe::OPENED_FROM;
use crate::views::recipe::use_label_names;
use crate::{DietSet, LabelSet, Route};
use dioxus::prelude::*;
use knife_core::input::NewRecipe as NewRecipeInput;
use knife_core::{Label, RecipeId, RecipeListing, Summary, simplify};
use std::cmp::Ordering;
use std::collections::HashMap;

/// Characters of label names shown per row before the rest become "+n".
const LABEL_BUDGET: usize = 24;

#[component]
pub fn RecipeList(labels: LabelSet, diets: DietSet) -> Element {
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
    // Open when arriving with labels or diets selected, as from a tag link.
    let mut open = use_signal(|| !labels.0.is_empty() || !diets.0.is_empty());

    // What is filtered beyond the search, listed under it when closed.
    let mut active = Vec::new();
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
    active.extend(diets.0.iter().map(|d| d.label().to_owned()));

    // The recipes left by the filters and the search, once loaded.
    let shown = match &*recipes.read() {
        Some(Ok(list)) => {
            let labelled: Vec<RecipeListing> = list
                .iter()
                .filter(|r| labels.0.is_subset(&r.tags))
                .filter(|r| diets.0.iter().all(|d| d.allows(r.classification)))
                .cloned()
                .collect();
            Some(fuzzy_filter(&labelled, |r| &r.name, &search.read()))
        }
        _ => None,
    };
    let mut recap = active.join(" · ");
    if let Some(shown) = &shown {
        let noun = if shown.len() == 1 {
            "recipe"
        } else {
            "recipes"
        };
        recap.push_str(&format!(" — {} {noun}", shown.len()));
    }

    rsx! {
        div { class: "title-row",
            h1 { "Recipes" }
            NewRecipeButton {}
        }
        div { class: "filters",
            div { class: "filters-head",
                SearchBox { value: search, placeholder: "Recipe name" }
                button {
                    class: "link",
                    r#type: "button",
                    "aria-expanded": open(),
                    onclick: move |_| open.toggle(),
                    "Filter"
                    if !active.is_empty() {
                        span { class: "badge", "{active.len()}" }
                    }
                    span { class: "chevron", "aria-hidden": "true", "▾" }
                }
            }
            if open() {
                div { class: "filters-body",
                    if let Some(Ok(all)) = &*all_labels.read() {
                        LabelFilter { labels: all.clone(), selected: labels.clone(), diets: diets.clone() }
                    }
                    DietFilter { labels: labels.clone(), selected: diets.clone() }
                }
            } else if !active.is_empty() {
                p { class: "active muted", "{recap}" }
            }
        }
        match (&*recipes.read(), shown) {
            (None, _) => rsx! { Loading {} },
            (Some(Err(e)), _) => rsx! { ErrorBanner { message: e.to_string() } },
            (Some(Ok(list)), shown) => {
                let shown = shown.unwrap_or_default();
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

/// The diets to filter the list by. Selecting a diet adds it to the page's
/// `?diets=`, selecting it again removes it; a recipe must fit them all.
#[component]
fn DietFilter(labels: LabelSet, selected: DietSet) -> Element {
    rsx! {
        p { class: "filter-heading", "Diet" }
        nav { class: "diet-filter", "aria-label": "Filter by diet",
            for diet in Diet::ALL {
                Link {
                    key: "{diet.slug()}",
                    class: if selected.0.contains(&diet) { "diet-chip selected" } else { "diet-chip" },
                    to: Route::RecipeList { labels: labels.clone(), diets: selected.toggled(diet) },
                    DietIcon { diet }
                    "{diet.label()}"
                }
            }
        }
    }
}

/// The labels to filter the list by. Selecting a label adds it to the page's
/// `?labels=`, selecting it again removes it, and "All" clears them.
#[component]
fn LabelFilter(labels: Vec<Label>, selected: LabelSet, diets: DietSet) -> Element {
    let mut labels: Vec<Label> = labels.into_iter().filter(|l| l.recipe_count > 0).collect();
    labels.sort_by_key(|l| l.simple_name.clone());
    if labels.is_empty() {
        return rsx! {};
    }

    rsx! {
        p { class: "filter-heading", "Labels" }
        nav { class: "label-filter", "aria-label": "Filter by label",
            Link {
                class: if selected.0.is_empty() { "tag plain selected" } else { "tag plain" },
                to: Route::RecipeList { labels: LabelSet::default(), diets: diets.clone() },
                "All"
            }
            for label in labels {
                Link {
                    key: "{label.simple_name}",
                    class: if selected.0.contains(&label.simple_name) { "tag plain tinted selected" } else { "tag plain tinted" },
                    style: tint(&label.simple_name),
                    to: Route::RecipeList { labels: selected.toggled(&label.simple_name), diets: diets.clone() },
                    "{label.name}"
                    span { class: "count", "{label.recipe_count}" }
                }
            }
        }
    }
}

/// A column the recipe table can be sorted by.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RecipeColumn {
    Name,
    Diet,
    Ingredients,
    Uses,
    Author,
}

impl SortColumn for RecipeColumn {
    type Item = RecipeListing;

    fn compare(self, a: &RecipeListing, b: &RecipeListing) -> Ordering {
        match self {
            Self::Name => simplify(&a.name).cmp(&simplify(&b.name)),
            // By how many diets the recipe fits.
            Self::Diet => diet_count(a).cmp(&diet_count(b)),
            Self::Ingredients => a.requirement_count.cmp(&b.requirement_count),
            Self::Uses => a.dependency_count.cmp(&b.dependency_count),
            // Recipes with no author last.
            Self::Author => (a.author.is_empty(), simplify(&a.author))
                .cmp(&(b.author.is_empty(), simplify(&b.author))),
        }
    }

    fn starts_descending(self) -> bool {
        matches!(self, Self::Diet | Self::Ingredients | Self::Uses)
    }
}

fn diet_count(recipe: &RecipeListing) -> usize {
    Diet::ALL
        .iter()
        .filter(|d| d.allows(recipe.classification))
        .count()
}

#[component]
fn RecipeTable(recipes: Vec<Match<RecipeListing>>) -> Element {
    let labels = use_label_names();
    let sort = use_signal(|| None::<(RecipeColumn, bool)>);
    let mut recipes = recipes;
    sort_rows(&mut recipes, sort());

    rsx! {
        table { class: "data recipes",
            thead {
                tr {
                    SortHeader { column: RecipeColumn::Name, sort, "Recipe" }
                    SortHeader { column: RecipeColumn::Diet, sort, "Diet" }
                    th { class: "labels", "Labels" }
                    SortHeader { column: RecipeColumn::Ingredients, sort, class: "count", "Ingredients" }
                    SortHeader { column: RecipeColumn::Uses, sort, class: "count uses", "Uses" }
                    SortHeader { column: RecipeColumn::Author, sort, class: "author", "From" }
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
                        td { class: "count", "{recipe.requirement_count}" }
                        td { class: "count uses",
                            if recipe.dependency_count > 0 {
                                "{recipe.dependency_count}"
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
                Link { key: "{tag}", class: "tag plain tinted", style: tint(tag), to: Route::RecipeList { labels: LabelSet::one(tag), diets: DietSet::default() }, "{name}" }
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

/// A "New recipe" button, opening a dialog asking for its name. The recipe
/// is then created and its edit page opened, to fill in the rest.
#[component]
pub fn NewRecipeButton() -> Element {
    let mut open = use_signal(|| false);
    rsx! {
        button { r#type: "button", onclick: move |_| open.set(true), "New recipe" }
        if open() {
            NewRecipeDialog { on_close: move |_| open.set(false) }
        }
    }
}

#[component]
fn NewRecipeDialog(on_close: EventHandler<()>) -> Element {
    let api = use_api();
    let navigator = use_navigator();
    let mutation = use_mutation();
    let mut name = use_signal(String::new);
    // A recipe holding the name, after a conflict.
    let mut taken_by = use_signal(|| None::<Summary<RecipeId>>);

    let submit = move |e: FormEvent| {
        e.prevent_default();
        let api = api.clone();
        taken_by.set(None);
        mutation.run(async move {
            let input = NewRecipeInput {
                name: name(),
                author: String::new(),
                directions: String::new(),
                information: String::new(),
            };
            match api.create_recipe(&input).await {
                Ok(recipe) => {
                    // The recipe page comes first, for "Done" to go back to.
                    navigator.push(Route::RecipePage {
                        id: recipe.id.0.clone(),
                    });
                    *OPENED_FROM.write() = Some(recipe.id.clone());
                    navigator.push(Route::EditRecipe { id: recipe.id.0 });
                    Ok(())
                }
                Err(e) => {
                    taken_by.set(e.existing());
                    Err(e)
                }
            }
        });
    };

    rsx! {
        div {
            class: "dialog-backdrop",
            onclick: move |_| on_close(()),
            onkeydown: move |e| {
                if e.key() == Key::Escape {
                    on_close(());
                }
            },
            form {
                class: "dialog compact",
                role: "dialog",
                "aria-modal": "true",
                "aria-label": "New recipe",
                onclick: move |e| e.stop_propagation(),
                onsubmit: submit,
                div { class: "dialog-head",
                    h2 { "New recipe" }
                    button {
                        r#type: "button",
                        class: "remove",
                        title: "Close",
                        onclick: move |_| on_close(()),
                        "×"
                    }
                }
                label {
                    "Name"
                    input {
                        required: true,
                        value: "{name}",
                        oninput: move |e| name.set(e.value()),
                        onmounted: move |e| async move {
                            _ = e.set_focus(true).await;
                        },
                    }
                }
                {mutation.banner()}
                if let Some(existing) = taken_by() {
                    p {
                        "See "
                        Link { to: Route::RecipePage { id: existing.id.0 }, "{existing.name}" }
                        "."
                    }
                }
                div { class: "row",
                    button { r#type: "submit", disabled: *mutation.busy.read(), "Create" }
                    button { r#type: "button", class: "secondary", onclick: move |_| on_close(()), "Cancel" }
                }
            }
        }
    }
}
