//! Labels, which recipes are tagged with: renamed, merged and deleted here. Their
//! recipes are the recipe list, filtered by label.

use crate::Error;
use crate::api::use_api;
use crate::components::{ErrorBanner, Loading, SearchBox, confirm, use_mutation};
use crate::{LabelSet, Route};
use dioxus::prelude::*;
use knife_core::input::LabelPatch;
use knife_core::{Label, simplify};

#[component]
pub fn LabelList() -> Element {
    let api = use_api();
    let search = use_signal(String::new);
    let mut labels = use_resource(move || {
        let api = api.clone();
        let prefix = search();
        async move { api.labels(&prefix).await }
    });

    rsx! {
        h1 { "Labels" }
        p { class: "muted", "Tag recipes from their edit page to create labels." }
        SearchBox { value: search, placeholder: "Search labels" }
        match &*labels.read() {
            None => rsx! { Loading {} },
            Some(Err(e)) => rsx! { ErrorBanner { message: e.to_string() } },
            Some(Ok(list)) if list.is_empty() => rsx! { p { class: "muted", "No labels found." } },
            Some(Ok(list)) => rsx! {
                ul { class: "label-rows",
                    for label in list.iter() {
                        LabelRow {
                            key: "{label.simple_name}",
                            label: label.clone(),
                            on_changed: move |_| labels.restart(),
                        }
                    }
                }
            },
        }
    }
}

/// What a label row is showing.
#[derive(Clone, Copy, PartialEq)]
enum Mode {
    View,
    Rename,
    Merge,
}

/// A label with its recipe count, renamed in place, merged into another or
/// deleted.
#[component]
fn LabelRow(label: Label, on_changed: EventHandler<()>) -> Element {
    let api = use_api();
    let mutation = use_mutation();
    let mut mode = use_signal(|| Mode::View);
    let mut name = use_signal(|| label.name.clone());

    let rename = {
        let (api, simple_name) = (api.clone(), label.simple_name.clone());
        move |e: FormEvent| {
            e.prevent_default();
            let (api, simple_name) = (api.clone(), simple_name.clone());
            mutation.run(async move {
                api.update_label(&simple_name, &LabelPatch { name: name() })
                    .await?;
                mode.set(Mode::View);
                on_changed(());
                Ok(())
            });
        }
    };

    let delete = {
        let (simple_name, display) = (label.simple_name.clone(), label.name.clone());
        move |_| {
            let question = format!("Delete the label {display}? Recipes keep everything else.");
            if !confirm(&question) {
                return;
            }
            let (api, simple_name) = (api.clone(), simple_name.clone());
            mutation.run(async move {
                api.delete_label(&simple_name).await?;
                on_changed(());
                Ok(())
            });
        }
    };

    let recipes = match label.recipe_count {
        1 => "1 recipe".to_owned(),
        n => format!("{n} recipes"),
    };

    rsx! {
        li {
            if mode() == Mode::Merge {
                MergeForm {
                    label: label.clone(),
                    on_merged: move |_| {
                        mode.set(Mode::View);
                        on_changed(());
                    },
                    on_cancel: move |_| mode.set(Mode::View),
                }
            } else if mode() == Mode::Rename {
                form { class: "row grow", onsubmit: rename,
                    input {
                        class: "grow",
                        required: true,
                        value: "{name}",
                        oninput: move |e| name.set(e.value()),
                    }
                    button {
                        r#type: "submit",
                        disabled: *mutation.busy.read() || name() == label.name,
                        "Rename"
                    }
                    button {
                        r#type: "button",
                        class: "secondary",
                        onclick: {
                            let original = label.name.clone();
                            move |_| {
                                name.set(original.clone());
                                mode.set(Mode::View);
                            }
                        },
                        "Cancel"
                    }
                }
            } else {
                Link {
                    class: "tag plain",
                    to: Route::RecipeList { labels: LabelSet::one(&label.simple_name) },
                    "{label.name}"
                }
                span { class: "muted", "{recipes}" }
                span { class: "actions",
                    button { class: "link", onclick: move |_| mode.set(Mode::Rename), "Rename" }
                    button { class: "link", onclick: move |_| mode.set(Mode::Merge), "Merge" }
                    button {
                        class: "link danger-text",
                        disabled: *mutation.busy.read(),
                        onclick: delete,
                        "Delete"
                    }
                }
            }
        }
        {mutation.banner()}
    }
}

/// Merges a label into another, such as two spellings of the same one: its
/// recipes take the other label, which may also be renamed.
#[component]
fn MergeForm(label: Label, on_merged: EventHandler<()>, on_cancel: EventHandler<()>) -> Element {
    let api = use_api();
    let mutation = use_mutation();
    let mut target = use_signal(String::new);
    let mut new_name = use_signal(String::new);

    let suggestions = use_resource({
        let api = api.clone();
        move || {
            let api = api.clone();
            let prefix = target();
            async move { api.labels(&prefix).await }
        }
    });
    // The label the typed name refers to, other than this one.
    let matched: Option<Label> = suggestions
        .read()
        .as_ref()
        .and_then(|r| r.as_ref().ok())
        .and_then(|list| {
            let wanted = simplify(&target.read());
            list.iter()
                .find(|l| l.simple_name == wanted && l.simple_name != label.simple_name)
                .cloned()
        });

    let submit = {
        let (label, matched) = (label.clone(), matched.clone());
        move |e: FormEvent| {
            e.prevent_default();
            let Some(into) = matched.clone() else {
                let mut error = mutation.error;
                error.set(Some(Error::NoSuchLabel(target()).to_string()));
                return;
            };
            let name = Some(new_name().trim().to_owned()).filter(|n| !n.is_empty());
            let final_name = name.clone().unwrap_or(into.name.clone());
            let question = format!(
                "Move {} recipe(s) from {} to {}, name it {final_name} and delete {}?",
                label.recipe_count, label.name, into.name, label.name
            );
            if !confirm(&question) {
                return;
            }
            let (api, from) = (api.clone(), label.clone());
            mutation.run(async move {
                api.merge_label(&from, &into, name).await?;
                on_merged(());
                Ok(())
            });
        }
    };

    rsx! {
        form { class: "stack grow", onsubmit: submit,
            p { class: "muted",
                "Merge {label.name} into another label. Its recipes take the other label, "
                "and {label.name} is deleted."
            }
            div { class: "row wrap",
                input {
                    class: "grow",
                    placeholder: "Label to keep",
                    list: "merge-labels-{label.simple_name}",
                    required: true,
                    value: "{target}",
                    oninput: move |e| target.set(e.value()),
                }
                datalist { id: "merge-labels-{label.simple_name}",
                    if let Some(Ok(list)) = &*suggestions.read() {
                        for l in list.iter().filter(|l| l.simple_name != label.simple_name) {
                            option { key: "{l.simple_name}", value: "{l.name}" }
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
