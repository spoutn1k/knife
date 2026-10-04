//! Ingredients and what they contain.

use crate::Route;
use crate::api::use_api;
use crate::components::{
    ContainsChecks, Diets, ErrorBanner, Loading, SearchBox, confirm, use_mutation,
};
use crate::views::recipes::RecipeLinks;
use dioxus::prelude::*;
use knife_core::input::{IngredientPatch, NewIngredient};
use knife_core::{Classification, IngredientDetails, IngredientId, Summary, simplify};

#[component]
pub fn IngredientList() -> Element {
    let api = use_api();
    let navigator = use_navigator();
    let search = use_signal(String::new);
    let ingredients = use_resource({
        let api = api.clone();
        move || {
            let api = api.clone();
            let prefix = search();
            async move { api.ingredients(&prefix).await }
        }
    });

    let mutation = use_mutation();
    let mut name = use_signal(String::new);
    let mut flags = use_signal(Classification::default);
    let create = move |e: FormEvent| {
        e.prevent_default();
        let api = api.clone();
        let c = flags();
        let input = NewIngredient {
            name: name(),
            dairy: c.dairy,
            meat: c.meat,
            gluten: c.gluten,
            animal_product: c.animal_product,
        };
        mutation.run(async move {
            let id = match api.create_ingredient(&input).await {
                Ok(ingredient) => ingredient.id,
                // Already there: show it rather than an error.
                Err(e) => e.existing::<Summary<IngredientId>>().ok_or(e)?.id,
            };
            navigator.push(Route::IngredientPage { id: id.0 });
            Ok(())
        });
    };

    rsx! {
        h1 { "Ingredients" }
        SearchBox { value: search, placeholder: "Search ingredients" }
        match &*ingredients.read() {
            None => rsx! { Loading {} },
            Some(Err(e)) => rsx! { ErrorBanner { message: e.to_string() } },
            Some(Ok(list)) if list.is_empty() => rsx! { p { class: "muted", "No ingredients found." } },
            Some(Ok(list)) => rsx! {
                ul { class: "links",
                    for ingredient in list.iter() {
                        li { key: "{ingredient.id}",
                            Link { to: Route::IngredientPage { id: ingredient.id.0.clone() }, "{ingredient.name}" }
                        }
                    }
                }
            },
        }
        form { class: "card stack", onsubmit: create,
            h2 { "New ingredient" }
            input {
                placeholder: "Name",
                required: true,
                value: "{name}",
                oninput: move |e| name.set(e.value()),
            }
            fieldset {
                legend { "It contains:" }
                ContainsChecks { value: flags(), onchange: move |c| flags.set(c) }
            }
            {mutation.banner()}
            div { class: "row",
                button { r#type: "submit", disabled: *mutation.busy.read(), "Create" }
            }
        }
    }
}

#[component]
pub fn IngredientPage(id: String) -> Element {
    let api = use_api();
    let mut details = use_resource(use_reactive!(|id| {
        let api = api.clone();
        async move { api.ingredient(&IngredientId(id)).await }
    }));

    match &*details.read() {
        None => rsx! { Loading {} },
        Some(Err(e)) => rsx! { ErrorBanner { message: e.to_string() } },
        // Keys only take effect in a list of children, hence the inner block:
        // another ingredient, such as after a merge, remounts the view,
        // resetting its fields.
        Some(Ok(current)) => rsx! {
            {rsx! {
                IngredientView {
                    key: "{current.ingredient.id}",
                    details: current.clone(),
                    on_saved: move |updated| details.set(Some(Ok(updated))),
                }
            }}
        },
    }
}

#[component]
fn IngredientView(
    details: IngredientDetails,
    on_saved: EventHandler<IngredientDetails>,
) -> Element {
    let api = use_api();
    let navigator = use_navigator();
    let mutation = use_mutation();
    let ingredient = &details.ingredient;
    let mut name = use_signal(|| ingredient.name.clone());

    // Saves a change and keeps the list of recipes, which it does not affect.
    let save = {
        let (api, details) = (api.clone(), details.clone());
        move |patch: IngredientPatch| {
            let (api, details) = (api.clone(), details.clone());
            mutation.run(async move {
                let ingredient = api
                    .update_ingredient(&details.ingredient.id, &patch)
                    .await?;
                on_saved(IngredientDetails {
                    ingredient,
                    ..details
                });
                Ok(())
            });
        }
    };

    let rename = {
        let save = save.clone();
        move |e: FormEvent| {
            e.prevent_default();
            save(IngredientPatch {
                name: Some(name()),
                ..Default::default()
            });
        }
    };

    let set_flags = move |c: Classification| {
        save(IngredientPatch {
            dairy: Some(c.dairy),
            meat: Some(c.meat),
            gluten: Some(c.gluten),
            animal_product: Some(c.animal_product),
            ..Default::default()
        })
    };

    let id = ingredient.id.clone();
    let label = ingredient.name.clone();
    let delete = move |_| {
        if !confirm(&format!("Delete {label}?")) {
            return;
        }
        let (api, id) = (api.clone(), id.clone());
        mutation.run(async move {
            api.delete_ingredient(&id).await?;
            navigator.push(Route::IngredientList {});
            Ok(())
        });
    };

    let used = !details.used_in.is_empty();

    rsx! {
        div { class: "title-row",
            h1 { "{ingredient.name}" }
            button {
                class: "danger",
                disabled: used || *mutation.busy.read(),
                title: if used { "Used by recipes: remove it from them first" } else { "" },
                onclick: delete,
                "Delete"
            }
        }
        Diets { classification: ingredient.classification }
        {mutation.banner()}
        form { class: "card stack", onsubmit: rename,
            label {
                "Name"
                div { class: "row",
                    input {
                        class: "grow",
                        required: true,
                        value: "{name}",
                        oninput: move |e| name.set(e.value()),
                    }
                    button {
                        r#type: "submit",
                        disabled: *mutation.busy.read() || name() == ingredient.name,
                        "Rename"
                    }
                }
            }
            fieldset {
                legend { "It contains:" }
                ContainsChecks { value: ingredient.classification, onchange: set_flags }
            }
        }
        h2 { "Used in" }
        if used {
            RecipeLinks { recipes: details.used_in.clone() }
        } else {
            p { class: "muted", "No recipe uses it." }
        }
        MergeForm { details: details.clone() }
    }
}

/// Merges this ingredient into another, such as two spellings of the same
/// thing: its recipes move to the other, which may also be renamed.
#[component]
fn MergeForm(details: IngredientDetails) -> Element {
    let api = use_api();
    let navigator = use_navigator();
    let mutation = use_mutation();
    let mut target = use_signal(String::new);
    let mut new_name = use_signal(String::new);
    let source = details.ingredient.clone();

    let suggestions = use_resource({
        let api = api.clone();
        move || {
            let api = api.clone();
            let prefix = target();
            async move { api.ingredients(&prefix).await }
        }
    });
    // The ingredient the typed name refers to, other than this one.
    let matched: Option<Summary<IngredientId>> = suggestions
        .read()
        .as_ref()
        .and_then(|r| r.as_ref().ok())
        .and_then(|list| {
            let wanted = simplify(&target.read());
            list.iter()
                .find(|s| simplify(&s.name) == wanted && s.id != source.id)
                .cloned()
        });

    let submit = {
        let (source, matched) = (source.clone(), matched.clone());
        let count = details.used_in.len();
        move |e: FormEvent| {
            e.prevent_default();
            let Some(into) = matched.clone() else {
                let mut error = mutation.error;
                error.set(Some(crate::Error::NoSuchIngredient(target()).to_string()));
                return;
            };
            let name = Some(new_name().trim().to_owned()).filter(|n| !n.is_empty());
            let final_name = name.clone().unwrap_or(into.name.clone());
            let question = format!(
                "Move {count} recipe(s) from {} to {}, name it {final_name} and delete {}?",
                source.name, into.name, source.name
            );
            if !confirm(&question) {
                return;
            }
            let (api, from) = (api.clone(), source.id.clone());
            mutation.run(async move {
                let merged = api.merge_ingredient(&from, &into.id, name).await?;
                navigator.replace(Route::IngredientPage { id: merged.id.0 });
                Ok(())
            });
        }
    };

    rsx! {
        form { class: "card stack", onsubmit: submit,
            h2 { "Merge into another ingredient" }
            p { class: "muted",
                "Every recipe using {source.name} will use the other ingredient instead, "
                "which also takes on what {source.name} contains. {source.name} is then deleted."
            }
            div { class: "row wrap",
                input {
                    class: "grow",
                    placeholder: "Ingredient to keep",
                    list: "merge-targets",
                    required: true,
                    value: "{target}",
                    oninput: move |e| target.set(e.value()),
                }
                datalist { id: "merge-targets",
                    if let Some(Ok(list)) = &*suggestions.read() {
                        for s in list.iter().filter(|s| s.id != source.id) {
                            option { key: "{s.id}", value: "{s.name}" }
                        }
                    }
                }
                input {
                    class: "grow",
                    placeholder: match &matched {
                        Some(m) => format!("New name (keeps “{}” if empty)", m.name),
                        None => "New name (optional)".to_owned(),
                    },
                    value: "{new_name}",
                    oninput: move |e| new_name.set(e.value()),
                }
            }
            {mutation.banner()}
            div { class: "row",
                button {
                    r#type: "submit",
                    disabled: *mutation.busy.read() || matched.is_none(),
                    if *mutation.busy.read() { "Merging…" } else { "Merge" }
                }
            }
        }
    }
}
