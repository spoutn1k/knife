//! Labels, which recipes are tagged with: renamed, merged and deleted here. Their
//! recipes are the recipe list, filtered by label.

use crate::Error;
use crate::api::use_api;
use crate::components::{
    ErrorBanner, Highlight, Loading, Match, MergeIcon, PenIcon, SearchBox, SortColumn, SortHeader,
    TrashIcon, confirm, fuzzy_filter, sort_rows, tint, use_mutation,
};
use crate::{DietSet, LabelSet, Route};
use dioxus::prelude::*;
use knife_core::input::LabelPatch;
use knife_core::{Label, simplify};
use std::cmp::Ordering;

#[component]
pub fn LabelList() -> Element {
    let api = use_api();
    let search = use_signal(String::new);
    let sort = use_signal(|| None::<(LabelColumn, bool)>);
    // Every label, loaded once and filtered here as the search is typed.
    let mut labels = use_resource(move || {
        let api = api.clone();
        async move { api.labels("").await }
    });

    rsx! {
        h1 { "Labels" }
        p { class: "muted", "Tag recipes from their edit page to create labels." }
        SearchBox { value: search, placeholder: "Search labels" }
        match &*labels.read() {
            None => rsx! { Loading {} },
            Some(Err(e)) => rsx! { ErrorBanner { message: e.to_string() } },
            Some(Ok(list)) if list.is_empty() => rsx! { p { class: "muted", "No labels yet." } },
            Some(Ok(list)) => {
                let mut shown = fuzzy_filter(list, |l| &l.name, &search.read());
                sort_rows(&mut shown, sort());
                if shown.is_empty() {
                    rsx! { p { class: "muted", "No label matches." } }
                } else {
                    rsx! {
                        table { class: "data label-rows",
                            thead {
                                tr {
                                    SortHeader { column: LabelColumn::Name, sort, "Label" }
                                    SortHeader { column: LabelColumn::Recipes, sort, class: "count", "Recipes" }
                                    th { class: "actions", "Actions" }
                                }
                            }
                            tbody {
                                for Match { item: label, indices } in shown {
                                    LabelRow {
                                        key: "{label.simple_name}",
                                        label,
                                        indices,
                                        on_changed: move |_| labels.restart(),
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

/// A column the label table can be sorted by.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum LabelColumn {
    Name,
    Recipes,
}

impl SortColumn for LabelColumn {
    type Item = Label;

    fn compare(self, a: &Label, b: &Label) -> Ordering {
        match self {
            Self::Name => a.simple_name.cmp(&b.simple_name),
            Self::Recipes => a.recipe_count.cmp(&b.recipe_count),
        }
    }

    fn starts_descending(self) -> bool {
        self == Self::Recipes
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
/// deleted. `indices` are the letters of its name matched by the search.
#[component]
fn LabelRow(label: Label, indices: Vec<u32>, on_changed: EventHandler<()>) -> Element {
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

    rsx! {
        tr {
            if mode() == Mode::Merge {
                td { class: "editing", colspan: 3,
                    MergeForm {
                        label: label.clone(),
                        on_merged: move |_| {
                            mode.set(Mode::View);
                            on_changed(());
                        },
                        on_cancel: move |_| mode.set(Mode::View),
                    }
                }
            } else if mode() == Mode::Rename {
                td { class: "editing", colspan: 3,
                    form { class: "row", onsubmit: rename,
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
                }
            } else {
                td {
                    Link {
                        class: "tag plain tinted",
                        style: tint(&label.simple_name),
                        to: Route::RecipeList { labels: LabelSet::one(&label.simple_name), diets: DietSet::default() },
                        Highlight { text: label.name.clone(), indices }
                    }
                }
                td { class: "count", "{label.recipe_count}" }
                td { class: "actions",
                    span { class: "icon-buttons",
                        button {
                            class: "icon-button",
                            title: "Rename",
                            "aria-label": "Rename {label.name}",
                            onclick: move |_| mode.set(Mode::Rename),
                            PenIcon {}
                        }
                        button {
                            class: "icon-button",
                            title: "Merge into another label",
                            "aria-label": "Merge {label.name}",
                            onclick: move |_| mode.set(Mode::Merge),
                            MergeIcon {}
                        }
                        button {
                            class: "icon-button danger",
                            title: "Delete",
                            "aria-label": "Delete {label.name}",
                            disabled: *mutation.busy.read(),
                            onclick: delete,
                            TrashIcon {}
                        }
                    }
                }
            }
        }
        if mutation.error.read().is_some() {
            tr { class: "error-row",
                td { colspan: 3, {mutation.banner()} }
            }
        }
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

    // Every label, suggested by the field, which filters them itself.
    let suggestions = use_resource({
        let api = api.clone();
        move || {
            let api = api.clone();
            async move { api.labels("").await }
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
                "Merge "
                span { class: "tag plain tinted", style: tint(&label.simple_name), "{label.name}" }
                " into another label. Its recipes take the other label, and "
                span { class: "tag plain tinted", style: tint(&label.simple_name), "{label.name}" }
                " is deleted."
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
