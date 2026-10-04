//! A recipe's edit page: its text, then its tags, ingredients and the
//! recipes it uses. Each change to those is saved as it is made.

use crate::api::{Api, use_api};
use crate::components::{ContainsChecks, ErrorBanner, Loading, confirm, use_mutation};
use crate::views::recipe::{by_group, use_label_names};
use crate::views::recipes::RecipeLinks;
use crate::{LabelSet, Route};
use dioxus::prelude::*;
use knife_core::input::{
    DependencyInput, NewIngredient, NewRecipe as NewRecipeInput, RecipePatch, RequirementInput,
};
use knife_core::{
    Classification, Dependency, IngredientId, Recipe, RecipeId, Requirement, Summary, simplify,
};

#[component]
pub fn EditRecipe(id: String) -> Element {
    let api = use_api();
    let mut recipe = use_resource(use_reactive!(|id| {
        let api = api.clone();
        async move { api.recipe(&RecipeId(id)).await }
    }));
    // Writes on this page return the updated recipe.
    let on_saved = move |updated: Recipe| recipe.set(Some(Ok(updated)));

    match &*recipe.read() {
        None => rsx! { Loading {} },
        Some(Err(e)) => rsx! { ErrorBanner { message: e.to_string() } },
        // Keys only take effect in a list of children, hence the inner block:
        // another recipe remounts the editor, resetting its forms.
        Some(Ok(recipe)) => rsx! {
            {rsx! {
                RecipeEditor { key: "{recipe.id}", recipe: recipe.clone(), on_saved }
            }}
        },
    }
}

#[component]
fn RecipeEditor(recipe: Recipe, on_saved: EventHandler<Recipe>) -> Element {
    let api = use_api();
    let navigator = use_navigator();
    let delete = use_mutation();
    // Recipes using this one, after a refused delete.
    let mut used_by = use_signal(Vec::<Summary<RecipeId>>::new);

    let id = recipe.id.clone();
    let name = recipe.name.clone();
    let delete_recipe = move |_| {
        if !confirm(&format!("Delete {name}?")) {
            return;
        }
        let (api, id) = (api.clone(), id.clone());
        delete.run(async move {
            match api.delete_recipe(&id).await {
                Ok(()) => {
                    navigator.push(Route::RecipeList {
                        labels: LabelSet::default(),
                    });
                    Ok(())
                }
                Err(e) => {
                    used_by.set(e.existing().unwrap_or_default());
                    Err(e)
                }
            }
        });
    };

    rsx! {
        div { class: "title-row",
            h1 { "Edit {recipe.name}" }
            div { class: "row",
                Link { class: "button", to: Route::RecipePage { id: recipe.id.0.clone() }, "Done" }
                button { class: "danger", disabled: *delete.busy.read(), onclick: delete_recipe, "Delete" }
            }
        }
        {delete.banner()}
        if !used_by.read().is_empty() {
            RecipeLinks { recipes: used_by() }
        }
        RecipeForm { recipe: Some(recipe.clone()), on_saved }
        div { class: "columns",
            section {
                h2 { "Ingredients" }
                Requirements { recipe: recipe.clone(), on_saved }
            }
            section {
                h2 { "Tags" }
                Tags { recipe: recipe.clone(), on_saved }
                h2 { "Uses" }
                Dependencies { recipe: recipe.clone(), on_saved }
            }
        }
    }
}

/// The text fields of a recipe. A new recipe opens its edit page once
/// created; an existing one stays there and passes the saved recipe to
/// `on_saved`.
#[component]
pub(super) fn RecipeForm(
    recipe: Option<Recipe>,
    on_saved: Option<EventHandler<Recipe>>,
) -> Element {
    let api = use_api();
    let navigator = use_navigator();
    let mutation = use_mutation();
    let field = |get: fn(&Recipe) -> &String| recipe.as_ref().map(get).cloned().unwrap_or_default();
    let mut name = use_signal(|| field(|r| &r.name));
    let mut author = use_signal(|| field(|r| &r.author));
    let mut directions = use_signal(|| field(|r| &r.directions));
    let mut information = use_signal(|| field(|r| &r.information));
    // A recipe holding the name, after a conflict on save.
    let mut taken_by = use_signal(|| None::<Summary<RecipeId>>);

    let dirty = recipe.as_ref().is_none_or(|r| {
        name() != r.name
            || author() != r.author
            || directions() != r.directions
            || information() != r.information
    });

    let original = recipe.clone();
    let submit = move |e: FormEvent| {
        e.prevent_default();
        let api = api.clone();
        let original = original.clone();
        taken_by.set(None);
        mutation.run(async move {
            let saved = match &original {
                None => {
                    let input = NewRecipeInput {
                        name: name(),
                        author: author(),
                        directions: directions(),
                        information: information(),
                    };
                    api.create_recipe(&input).await
                }
                Some(original) => {
                    let changed = |new: String, old: &String| (new != *old).then_some(new);
                    let patch = RecipePatch {
                        name: changed(name(), &original.name),
                        author: changed(author(), &original.author),
                        directions: changed(directions(), &original.directions),
                        information: changed(information(), &original.information),
                    };
                    if patch == RecipePatch::default() {
                        Ok(original.clone())
                    } else {
                        api.update_recipe(&original.id, &patch).await
                    }
                }
            };
            match saved {
                Ok(recipe) => {
                    match on_saved {
                        Some(on_saved) => on_saved(recipe),
                        None => {
                            navigator.push(Route::EditRecipe { id: recipe.id.0 });
                        }
                    }
                    Ok(())
                }
                Err(e) => {
                    taken_by.set(e.existing());
                    Err(e)
                }
            }
        });
    };

    let original = recipe.clone();
    let revert = move |_| {
        if let Some(r) = &original {
            name.set(r.name.clone());
            author.set(r.author.clone());
            directions.set(r.directions.clone());
            information.set(r.information.clone());
        }
    };

    rsx! {
        form { class: "card stack", onsubmit: submit,
            label {
                "Name"
                input {
                    required: true,
                    value: "{name}",
                    oninput: move |e| name.set(e.value()),
                }
            }
            label {
                "From"
                input {
                    placeholder: "Grandma, a book, a website…",
                    value: "{author}",
                    oninput: move |e| author.set(e.value()),
                }
            }
            label {
                span {
                    "Directions "
                    span { class: "muted", "(markdown)" }
                }
                textarea {
                    rows: 12,
                    value: "{directions}",
                    oninput: move |e| directions.set(e.value()),
                }
            }
            label {
                span {
                    "Notes "
                    span { class: "muted", "(markdown)" }
                }
                textarea {
                    rows: 4,
                    placeholder: "Servings, timing, variations…",
                    value: "{information}",
                    oninput: move |e| information.set(e.value()),
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
                if recipe.is_some() {
                    button { r#type: "submit", disabled: !dirty || *mutation.busy.read(), "Save" }
                    if dirty {
                        button { r#type: "button", class: "secondary", onclick: revert, "Revert" }
                        span { class: "muted", "Unsaved changes" }
                    }
                } else {
                    button { r#type: "submit", disabled: *mutation.busy.read(), "Create" }
                    Link { class: "button secondary", to: Route::RecipeList { labels: LabelSet::default() }, "Cancel" }
                }
            }
        }
    }
}

// --- Tags --------------------------------------------------------------------

#[component]
fn Tags(recipe: Recipe, on_saved: EventHandler<Recipe>) -> Element {
    let api = use_api();
    let mutation = use_mutation();
    let mut new_tag = use_signal(String::new);
    let names = use_label_names();

    let id = recipe.id.clone();
    let add = {
        let api = api.clone();
        let id = id.clone();
        move |e: FormEvent| {
            e.prevent_default();
            let (api, id, label) = (api.clone(), id.clone(), new_tag());
            mutation.run(async move {
                on_saved(api.put_tag(&id, &label).await?);
                new_tag.set(String::new());
                Ok(())
            });
        }
    };

    rsx! {
        div { class: "tags",
            for tag in recipe.tags.iter().cloned() {
                span { key: "{tag}", class: "tag",
                    Link { to: Route::RecipeList { labels: LabelSet::one(&tag) },
                        {names.get(&tag).cloned().unwrap_or(tag.clone())}
                    }
                    button {
                        class: "remove",
                        title: "Remove this tag",
                        onclick: {
                            let (api, id, tag) = (api.clone(), id.clone(), tag.clone());
                            move |_| {
                                let (api, id, tag) = (api.clone(), id.clone(), tag.clone());
                                mutation.run(async move {
                                    on_saved(api.delete_tag(&id, &tag).await?);
                                    Ok(())
                                });
                            }
                        },
                        "×"
                    }
                }
            }
            form { class: "inline", onsubmit: add,
                input {
                    list: "label-names",
                    placeholder: "Add a tag",
                    size: 12,
                    value: "{new_tag}",
                    oninput: move |e| new_tag.set(e.value()),
                }
                datalist { id: "label-names",
                    for name in names.values() {
                        option { value: "{name}" }
                    }
                }
            }
        }
        {mutation.banner()}
    }
}

// --- Requirements ------------------------------------------------------------

#[component]
fn Requirements(recipe: Recipe, on_saved: EventHandler<Recipe>) -> Element {
    let api = use_api();
    let mutation = use_mutation();
    // The requirement being edited in the form, if any.
    let mut editing = use_signal(|| None::<(IngredientId, Requirement)>);
    // Bumped after each save, to reset the form.
    let mut saves = use_signal(|| 0u32);

    let groups = by_group(&recipe);
    let group_names: Vec<String> = groups
        .keys()
        .filter(|g| !g.is_empty())
        .map(|g| g.to_string())
        .collect();

    let remove = move |recipe_id: RecipeId, ingredient: IngredientId| {
        let api = api.clone();
        move |_| {
            let (api, recipe_id, ingredient) = (api.clone(), recipe_id.clone(), ingredient.clone());
            mutation.run(async move {
                on_saved(api.delete_requirement(&recipe_id, &ingredient).await?);
                Ok(())
            });
        }
    };

    let form_key = match &*editing.read() {
        Some((id, _)) => format!("{}-{id}", saves()),
        None => format!("{}-new", saves()),
    };

    rsx! {
        if recipe.requirements.is_empty() {
            p { class: "muted", "No ingredients yet." }
        }
        for (group, list) in groups {
            div { key: "{group}",
            if !group.is_empty() {
                h3 { "{group}" }
            }
            ul { class: "requirements",
                for (ingredient, requirement) in list {
                    li { key: "{ingredient}",
                        span { class: "quantity", "{requirement.quantity}" }
                        Link { to: Route::IngredientPage { id: ingredient.0.clone() }, "{requirement.name}" }
                        if requirement.optional {
                            span { class: "muted", " (optional)" }
                        }
                        span { class: "actions",
                            button {
                                class: "link",
                                onclick: {
                                    let entry = (ingredient.clone(), requirement.clone());
                                    move |_| editing.set(Some(entry.clone()))
                                },
                                "Edit"
                            }
                            button {
                                class: "remove",
                                title: "Remove this ingredient",
                                onclick: remove(recipe.id.clone(), ingredient.clone()),
                                "×"
                            }
                        }
                    }
                }
            }
            }
        }
        {mutation.banner()}
        // Keyed so that a save or a new edit starts from a fresh form.
        {rsx! {
            RequirementForm {
                key: "{form_key}",
                recipe_id: recipe.id.clone(),
                editing: editing(),
                groups: group_names,
                on_saved: move |updated| {
                    editing.set(None);
                    saves += 1;
                    on_saved(updated);
                },
                on_cancel: move |_| editing.set(None),
            }
        }}
    }
}

/// Adds an ingredient to the recipe, creating the ingredient if it is new,
/// or changes an existing requirement.
#[component]
fn RequirementForm(
    recipe_id: RecipeId,
    editing: Option<(IngredientId, Requirement)>,
    groups: Vec<String>,
    on_saved: EventHandler<Recipe>,
    on_cancel: EventHandler<()>,
) -> Element {
    let api = use_api();
    let mutation = use_mutation();
    let existing = editing.as_ref().map(|(_, r)| r.clone());
    let mut name = use_signal(|| {
        existing
            .as_ref()
            .map(|r| r.name.clone())
            .unwrap_or_default()
    });
    let mut quantity = use_signal(|| {
        existing
            .as_ref()
            .map(|r| r.quantity.clone())
            .unwrap_or_default()
    });
    let mut group = use_signal(|| {
        existing
            .as_ref()
            .map(|r| r.group.clone())
            .unwrap_or_default()
    });
    let mut optional = use_signal(|| existing.as_ref().is_some_and(|r| r.optional));
    // Flags for an ingredient created by this form.
    let mut flags = use_signal(Classification::default);

    let suggestions = use_resource({
        let api = api.clone();
        move || {
            let api = api.clone();
            let prefix = name();
            async move { api.ingredients(&prefix).await }
        }
    });
    // The ingredient the typed name refers to, if it exists.
    let matched: Option<IngredientId> = match &editing {
        Some((id, _)) => Some(id.clone()),
        None => suggestions
            .read()
            .as_ref()
            .and_then(|r| r.as_ref().ok())
            .and_then(|list| {
                let wanted = simplify(&name.read());
                list.iter()
                    .find(|s| simplify(&s.name) == wanted)
                    .map(|s| s.id.clone())
            }),
    };
    let is_new =
        matched.is_none() && !simplify(&name.read()).is_empty() && suggestions.read().is_some();

    let submit = {
        let matched = matched.clone();
        move |e: FormEvent| {
            e.prevent_default();
            let (api, recipe_id, matched) = (api.clone(), recipe_id.clone(), matched.clone());
            mutation.run(async move {
                let ingredient = match matched {
                    Some(id) => id,
                    None => create_ingredient(&api, name(), flags()).await?,
                };
                let input = RequirementInput {
                    quantity: quantity().trim().to_owned(),
                    optional: optional(),
                    group: group().trim().to_owned(),
                };
                on_saved(api.put_requirement(&recipe_id, &ingredient, &input).await?);
                Ok(())
            });
        }
    };

    rsx! {
        form { class: "card stack", onsubmit: submit,
            h3 {
                if editing.is_some() { "Change {name}" } else { "Add an ingredient" }
            }
            div { class: "row wrap",
                input {
                    class: "grow",
                    placeholder: "Ingredient",
                    list: "ingredient-names",
                    required: true,
                    disabled: editing.is_some(),
                    value: "{name}",
                    oninput: move |e| name.set(e.value()),
                }
                datalist { id: "ingredient-names",
                    if let Some(Ok(list)) = &*suggestions.read() {
                        for s in list.iter() {
                            option { key: "{s.id}", value: "{s.name}" }
                        }
                    }
                }
                input {
                    placeholder: "Quantity",
                    size: 10,
                    required: true,
                    value: "{quantity}",
                    oninput: move |e| quantity.set(e.value()),
                }
            }
            div { class: "row wrap",
                input {
                    class: "grow",
                    placeholder: "Group, such as “for the sauce”",
                    list: "group-names",
                    value: "{group}",
                    oninput: move |e| group.set(e.value()),
                }
                datalist { id: "group-names",
                    for g in groups {
                        option { value: "{g}" }
                    }
                }
                label { class: "check",
                    input {
                        r#type: "checkbox",
                        checked: optional(),
                        onchange: move |e| optional.set(e.checked()),
                    }
                    "Optional"
                }
            }
            if is_new {
                fieldset {
                    legend { "New ingredient. It contains:" }
                    ContainsChecks { value: flags(), onchange: move |c| flags.set(c) }
                }
            }
            {mutation.banner()}
            div { class: "row",
                button { r#type: "submit", disabled: *mutation.busy.read(),
                    if editing.is_some() { "Save" } else { "Add" }
                }
                if editing.is_some() {
                    button {
                        r#type: "button",
                        class: "secondary",
                        onclick: move |_| on_cancel(()),
                        "Cancel"
                    }
                }
            }
        }
    }
}

/// Create an ingredient, or reuse the one already holding its name.
async fn create_ingredient(
    api: &Api,
    name: String,
    flags: Classification,
) -> crate::api::Result<IngredientId> {
    let input = NewIngredient {
        name,
        dairy: flags.dairy,
        meat: flags.meat,
        gluten: flags.gluten,
        animal_product: flags.animal_product,
    };
    match api.create_ingredient(&input).await {
        Ok(ingredient) => Ok(ingredient.id),
        Err(e) => match e.existing::<Summary<IngredientId>>() {
            Some(existing) => Ok(existing.id),
            None => Err(e),
        },
    }
}

// --- Dependencies ------------------------------------------------------------

#[component]
fn Dependencies(recipe: Recipe, on_saved: EventHandler<Recipe>) -> Element {
    let api = use_api();
    let mutation = use_mutation();
    // The dependency being edited in the form, if any.
    let mut editing = use_signal(|| None::<(RecipeId, Dependency)>);
    // Bumped after each save, to reset the form.
    let mut saves = use_signal(|| 0u32);

    let mut dependencies: Vec<_> = recipe.dependencies.iter().collect();
    dependencies.sort_by_key(|(_, d)| simplify(&d.name));

    let form_key = match &*editing.read() {
        Some((id, _)) => format!("{}-{id}", saves()),
        None => format!("{}-new", saves()),
    };

    rsx! {
        if dependencies.is_empty() {
            p { class: "muted", "No other recipes." }
        }
        ul { class: "requirements",
            for (requisite, dependency) in dependencies {
                li { key: "{requisite}",
                    span { class: "quantity", "{dependency.quantity}" }
                    Link { to: Route::RecipePage { id: requisite.0.clone() }, "{dependency.name}" }
                    if dependency.optional {
                        span { class: "muted", " (optional)" }
                    }
                    span { class: "actions",
                        button {
                            class: "link",
                            onclick: {
                                let entry = (requisite.clone(), dependency.clone());
                                move |_| editing.set(Some(entry.clone()))
                            },
                            "Edit"
                        }
                        button {
                            class: "remove",
                            title: "Stop using this recipe",
                            onclick: {
                                let (api, id, requisite) = (api.clone(), recipe.id.clone(), requisite.clone());
                                move |_| {
                                    let (api, id, requisite) = (api.clone(), id.clone(), requisite.clone());
                                    mutation.run(async move {
                                        on_saved(api.delete_dependency(&id, &requisite).await?);
                                        Ok(())
                                    });
                                }
                            },
                            "×"
                        }
                    }
                }
            }
        }
        {mutation.banner()}
        // Keyed so that a save or a new edit starts from a fresh form.
        {rsx! {
            DependencyForm {
                key: "{form_key}",
                recipe_id: recipe.id.clone(),
                editing: editing(),
                on_saved: move |updated| {
                    editing.set(None);
                    saves += 1;
                    on_saved(updated);
                },
                on_cancel: move |_| editing.set(None),
            }
        }}
    }
}

/// Makes the recipe use another, or changes how much of it it uses.
#[component]
fn DependencyForm(
    recipe_id: RecipeId,
    editing: Option<(RecipeId, Dependency)>,
    on_saved: EventHandler<Recipe>,
    on_cancel: EventHandler<()>,
) -> Element {
    let api = use_api();
    let mutation = use_mutation();
    let existing = editing.as_ref().map(|(_, d)| d.clone());
    let mut name = use_signal(|| {
        existing
            .as_ref()
            .map(|d| d.name.clone())
            .unwrap_or_default()
    });
    let mut quantity = use_signal(|| {
        existing
            .as_ref()
            .map(|d| d.quantity.clone())
            .unwrap_or_default()
    });
    let mut optional = use_signal(|| existing.as_ref().is_some_and(|d| d.optional));

    let suggestions = use_resource({
        let api = api.clone();
        move || {
            let api = api.clone();
            let prefix = name();
            async move { api.recipes(&prefix).await }
        }
    });
    // The recipe the typed name refers to, if it exists.
    let matched: Option<RecipeId> = match &editing {
        Some((id, _)) => Some(id.clone()),
        None => suggestions
            .read()
            .as_ref()
            .and_then(|r| r.as_ref().ok())
            .and_then(|list| {
                let wanted = simplify(&name.read());
                list.iter()
                    .find(|s| simplify(&s.name) == wanted)
                    .map(|s| s.id.clone())
            }),
    };

    let submit = {
        let recipe_id = recipe_id.clone();
        move |e: FormEvent| {
            e.prevent_default();
            let (api, id, matched) = (api.clone(), recipe_id.clone(), matched.clone());
            mutation.run(async move {
                let Some(requisite) = matched else {
                    return Err(crate::Error::NoSuchRecipe(name()));
                };
                let input = DependencyInput {
                    quantity: quantity().trim().to_owned(),
                    optional: optional(),
                };
                on_saved(api.put_dependency(&id, &requisite, &input).await?);
                Ok(())
            });
        }
    };

    rsx! {
        form { class: "card stack", onsubmit: submit,
            h3 {
                if editing.is_some() { "Change {name}" } else { "Use another recipe" }
            }
            div { class: "row wrap",
                input {
                    class: "grow",
                    placeholder: "Recipe, such as a sauce or a dough",
                    list: "recipe-names",
                    required: true,
                    disabled: editing.is_some(),
                    value: "{name}",
                    oninput: move |e| name.set(e.value()),
                }
                datalist { id: "recipe-names",
                    if let Some(Ok(list)) = &*suggestions.read() {
                        for s in list.iter().filter(|s| s.id != recipe_id) {
                            option { key: "{s.id}", value: "{s.name}" }
                        }
                    }
                }
                input {
                    placeholder: "Quantity",
                    size: 10,
                    value: "{quantity}",
                    oninput: move |e| quantity.set(e.value()),
                }
                label { class: "check",
                    input {
                        r#type: "checkbox",
                        checked: optional(),
                        onchange: move |e| optional.set(e.checked()),
                    }
                    "Optional"
                }
            }
            {mutation.banner()}
            div { class: "row",
                button { r#type: "submit", disabled: *mutation.busy.read(),
                    if editing.is_some() { "Save" } else { "Add" }
                }
                if editing.is_some() {
                    button {
                        r#type: "button",
                        class: "secondary",
                        onclick: move |_| on_cancel(()),
                        "Cancel"
                    }
                }
            }
        }
    }
}
