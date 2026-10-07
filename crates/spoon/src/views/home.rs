//! The landing page: a search over every recipe, then themes such as
//! cuisines, each showing a few of its labels with some of their recipes.

use crate::api::use_api;
use crate::components::{
    DietIcons, ErrorBanner, Highlight, Loading, Match, SearchBox, fnv, fuzzy_filter, tint,
};
use crate::views::recipes::NewRecipeButton;
use crate::{DietSet, LabelSet, Route};
use dioxus::prelude::*;
use knife_core::{Label, RecipeListing, simplify};

/// A titled group of labels on the landing page.
struct Theme {
    title: &'static str,
    /// Label names, matched as [`simplify`] spells them.
    labels: &'static [&'static str],
}

/// The themes, in page order. Each shows [`SHELVES`] of its labels, picked
/// at random among those with recipes; one with none is left out.
const THEMES: &[Theme] = &[
    Theme {
        title: "Cuisines",
        labels: &["français", "italien", "japonais", "coreen", "oriental", "tex-mex", "mexicain"],
    },
    Theme {
        title: "Sain",
        labels: &["soupe", "salade", "leger", "poisson"],
    },
];

/// Labels shown per theme.
const SHELVES: usize = 4;
/// Recipes shown per label.
const PER_SHELF: usize = 4;

#[component]
pub fn Home() -> Element {
    let api = use_api();
    let search = use_signal(String::new);
    // Picks the labels shown, anew on each visit but not while searching.
    let seed = use_hook(|| (js_sys::Math::random() * f64::from(u32::MAX)) as u32);
    let recipes = use_resource({
        let api = api.clone();
        move || {
            let api = api.clone();
            async move { api.recipes("").await }
        }
    });
    let labels = use_resource(move || {
        let api = api.clone();
        async move { api.labels("").await }
    });

    let count = match &*recipes.read() {
        Some(Ok(list)) => list.len(),
        _ => 0,
    };
    let placeholder = match count {
        0 => "Search recipes".to_owned(),
        1 => "Search 1 recipe".to_owned(),
        n => format!("Search {n} recipes"),
    };

    rsx! {
        div { class: "hero",
            div { class: "grow",
                h1 { "What are we cooking?" }
                SearchBox { value: search, placeholder }
            }
            NewRecipeButton {}
        }
        match (&*recipes.read(), &*labels.read()) {
            (Some(Err(e)), _) | (_, Some(Err(e))) => rsx! { ErrorBanner { message: e.to_string() } },
            (Some(Ok(recipes)), Some(Ok(labels))) => {
                if recipes.is_empty() {
                    rsx! { p { class: "muted", "No recipes yet." } }
                } else if search.read().trim().is_empty() {
                    rsx! { Themes { recipes: recipes.clone(), labels: labels.clone(), seed } }
                } else {
                    let found = fuzzy_filter(recipes, |r| &r.name, &search.read());
                    rsx! { Results { recipes: found } }
                }
            }
            _ => rsx! { Loading {} },
        }
    }
}

/// Each theme as a title over a 2×2 grid of its labels, each with a few of
/// its recipes.
#[component]
fn Themes(recipes: Vec<RecipeListing>, labels: Vec<Label>, seed: u32) -> Element {
    let mut sorted = recipes;
    sorted.sort_by(|a, b| a.name.cmp(&b.name));
    let used = labels.iter().filter(|l| l.recipe_count > 0).count();

    let themes: Vec<(&str, Vec<&Label>)> = THEMES
        .iter()
        .map(|theme| {
            let wanted: Vec<String> = theme.labels.iter().map(|l| simplify(l)).collect();
            let mut picked: Vec<&Label> = labels
                .iter()
                .filter(|l| l.recipe_count > 0 && wanted.contains(&l.simple_name))
                .collect();
            picked.sort_by_key(|l| fnv(seed, &l.simple_name));
            picked.truncate(SHELVES);
            (theme.title, picked)
        })
        .filter(|(_, picked)| !picked.is_empty())
        .collect();

    rsx! {
        for (title, picked) in themes {
            section { key: "{title}", class: "theme",
                h2 { "{title}" }
                div { class: "shelves",
                    for label in picked {
                        Shelf {
                            key: "{label.simple_name}",
                            label: label.clone(),
                            recipes: sorted
                                .iter()
                                .filter(|r| r.tags.contains(&label.simple_name))
                                .take(PER_SHELF)
                                .cloned()
                                .collect::<Vec<_>>(),
                        }
                    }
                }
            }
        }
        p { class: "muted",
            "More in "
            Link { to: Route::RecipeList { labels: LabelSet::default(), diets: DietSet::default() }, "all recipes" }
            if used > 0 {
                " and "
                Link { to: Route::LabelList {}, "all {used} labels" }
            }
            "."
        }
    }
}

/// A label, in its own color, over a 2×2 grid of its recipes.
#[component]
fn Shelf(label: Label, recipes: Vec<RecipeListing>) -> Element {
    let filtered = Route::RecipeList {
        labels: LabelSet::one(&label.simple_name),
        diets: DietSet::default(),
    };
    rsx! {
        section { class: "shelf tinted", style: tint(&label.simple_name),
            div { class: "shelf-head",
                h3 {
                    Link { class: "shelf-name", to: filtered.clone(), "{label.name}" }
                    span { class: "muted", "{label.recipe_count} {plural(label.recipe_count as usize)}" }
                }
                Link { class: "see-all", to: filtered, "See all →" }
            }
            div { class: "shelf-cards",
                for recipe in recipes {
                    RecipeCard { key: "{recipe.id}", recipe, indices: Vec::new() }
                }
            }
        }
    }
}

/// The recipes matching the search, best first.
#[component]
fn Results(recipes: Vec<Match<RecipeListing>>) -> Element {
    if recipes.is_empty() {
        return rsx! { p { class: "muted", "No recipe matches." } };
    }
    rsx! {
        p { class: "muted", "{recipes.len()} {plural(recipes.len())}" }
        div { class: "card-grid",
            for Match { item, indices } in recipes {
                RecipeCard { key: "{item.id}", recipe: item, indices }
            }
        }
    }
}

#[component]
fn RecipeCard(recipe: RecipeListing, indices: Vec<u32>) -> Element {
    rsx! {
        Link { class: "recipe-card", to: Route::RecipePage { id: recipe.id.0.clone() },
            span { class: "name", Highlight { text: recipe.name.clone(), indices } }
            if !recipe.author.is_empty() {
                span { class: "author", "{recipe.author}" }
            }
            DietIcons { classification: recipe.classification }
        }
    }
}

fn plural(n: usize) -> &'static str {
    if n == 1 { "recipe" } else { "recipes" }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn theme_labels_are_simple_names() {
        assert_eq!(simplify(THEMES[0].labels[0]), "francais");
    }

    #[test]
    fn seeds_change_the_order() {
        let order = |seed| {
            let mut names = ["francais", "italien", "japonais", "mexicain", "libanais"];
            names.sort_by_key(|n| fnv(seed, n));
            names
        };
        assert_eq!(order(1), order(1));
        assert!((2..20).any(|seed| order(seed) != order(1)));
    }
}
