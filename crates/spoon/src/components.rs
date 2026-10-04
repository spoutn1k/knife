//! Pieces shared by several pages.

use crate::Error;
use dioxus::prelude::*;
use knife_core::Classification;
use std::future::Future;

#[component]
pub fn Loading() -> Element {
    rsx! { p { class: "muted loading", "Loading…" } }
}

#[component]
pub fn ErrorBanner(message: String) -> Element {
    rsx! { p { class: "error", role: "alert", "{message}" } }
}

/// Recipe text written in markdown.
#[component]
pub fn Markdown(text: String) -> Element {
    rsx! { div { class: "markdown", dangerous_inner_html: crate::markdown::to_html(&text) } }
}

/// What a recipe or ingredient is safe for, from its classification.
#[component]
pub fn Diets(classification: Classification) -> Element {
    rsx! {
        ul { class: "diets",
            for diet in Diet::of(classification) {
                li { title: diet.label(),
                    DietIcon { diet }
                    "{diet.label()}"
                }
            }
        }
    }
}

/// [`Diets`] as icons alone, for tables. Hovering one names it.
#[component]
pub fn DietIcons(classification: Classification) -> Element {
    rsx! {
        span { class: "diet-icons",
            for diet in Diet::of(classification) {
                span { title: diet.label(), "aria-label": diet.label(), role: "img",
                    DietIcon { diet }
                }
            }
        }
    }
}

#[derive(Clone, Copy, PartialEq)]
pub enum Diet {
    Vegan,
    Vegetarian,
    DairyFree,
    GlutenFree,
}

impl Diet {
    /// The diets a classification allows. Vegan implies vegetarian, so only
    /// the stronger of the two is listed.
    pub fn of(c: Classification) -> Vec<Self> {
        let vegan = !c.meat && !c.dairy && !c.animal_product;
        [
            (Self::Vegan, vegan),
            (Self::Vegetarian, !c.meat && !vegan),
            (Self::DairyFree, !c.dairy),
            (Self::GlutenFree, !c.gluten),
        ]
        .into_iter()
        .filter_map(|(diet, applies)| applies.then_some(diet))
        .collect()
    }

    pub fn label(self) -> &'static str {
        match self {
            Self::Vegan => "Vegan",
            Self::Vegetarian => "Vegetarian",
            Self::DairyFree => "Dairy-free",
            Self::GlutenFree => "Gluten-free",
        }
    }
}

/// A line icon for a diet, drawn in the text colour: a leaf for vegetarian
/// and vegan, a crossed-out milk drop or wheat ear for the others.
#[component]
pub fn DietIcon(diet: Diet) -> Element {
    let strike = rsx! { path { d: "M4 4 20 20" } };
    let shape = match diet {
        Diet::Vegan | Diet::Vegetarian => rsx! {
            path { d: "M5 19C5 10 10 5 19 5c0 9-5 14-14 14Z" }
            path { d: "M5 19 13 11" }
        },
        Diet::DairyFree => rsx! {
            path { d: "M12 3s-6 7-6 11a6 6 0 0 0 12 0c0-4-6-11-6-11Z" }
            {strike}
        },
        Diet::GlutenFree => rsx! {
            path { d: "M12 21V9" }
            path { d: "M12 9c-2.5 0-3.5-2-3.5-4.5C11 4.5 12 6.5 12 9Zm0 0c2.5 0 3.5-2 3.5-4.5C13 4.5 12 6.5 12 9Z" }
            path { d: "M12 14c-2.5 0-3.5-2-3.5-4.5 2.5 0 3.5 2 3.5 4.5Zm0 0c2.5 0 3.5-2 3.5-4.5-2.5 0-3.5 2-3.5 4.5Z" }
            {strike}
        },
    };

    rsx! {
        svg {
            class: "icon",
            "aria-hidden": "true",
            view_box: "0 0 24 24",
            fill: "none",
            stroke: "currentColor",
            stroke_width: "2",
            stroke_linecap: "round",
            stroke_linejoin: "round",
            {shape}
        }
    }
}

/// A pen, for edit buttons shown as icons.
#[component]
pub fn PenIcon() -> Element {
    rsx! {
        svg {
            class: "icon",
            "aria-hidden": "true",
            view_box: "0 0 24 24",
            fill: "none",
            stroke: "currentColor",
            stroke_width: "2",
            stroke_linecap: "round",
            stroke_linejoin: "round",
            path { d: "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" }
            path { d: "M14.5 5.5 18.5 9.5" }
        }
    }
}

/// A search field for a prefix filter.
#[component]
pub fn SearchBox(value: Signal<String>, placeholder: String) -> Element {
    rsx! {
        input {
            class: "search",
            r#type: "search",
            placeholder,
            value: "{value}",
            oninput: move |e| value.set(e.value()),
        }
    }
}

/// The state of a user-triggered write: whether it is running, and why the
/// last one failed.
#[derive(Clone, Copy, PartialEq)]
pub struct Mutation {
    pub busy: Signal<bool>,
    pub error: Signal<Option<String>>,
}

pub fn use_mutation() -> Mutation {
    Mutation {
        busy: use_signal(|| false),
        error: use_signal(|| None),
    }
}

impl Mutation {
    /// Run `work`, keeping its error to show. Ignored while a previous call
    /// is still running, so a double click does not send twice.
    pub fn run(mut self, work: impl Future<Output = Result<(), Error>> + 'static) {
        if *self.busy.peek() {
            return;
        }
        self.busy.set(true);
        self.error.set(None);
        spawn(async move {
            let result = work.await;
            self.busy.set(false);
            if let Err(e) = result {
                self.error.set(Some(e.to_string()));
            }
        });
    }

    /// The last error, as a banner.
    pub fn banner(self) -> Element {
        match self.error.read().as_ref() {
            Some(message) => rsx! { ErrorBanner { message: message.clone() } },
            None => rsx! {},
        }
    }
}

/// Ask the browser to confirm a destructive action.
pub fn confirm(message: &str) -> bool {
    web_sys::window()
        .and_then(|w| w.confirm_with_message(message).ok())
        .unwrap_or(false)
}

/// One of a [`Classification`]'s flags.
type Flag = fn(&mut Classification) -> &mut bool;

/// Checkboxes for what an ingredient contains.
#[component]
pub fn ContainsChecks(value: Classification, onchange: EventHandler<Classification>) -> Element {
    let flags: [(&str, Flag); 4] = [
        ("Meat", |c| &mut c.meat),
        ("Dairy", |c| &mut c.dairy),
        ("Other animal product", |c| &mut c.animal_product),
        ("Gluten", |c| &mut c.gluten),
    ];

    rsx! {
        div { class: "row wrap",
            for (label, field) in flags {
                label { class: "check",
                    input {
                        r#type: "checkbox",
                        checked: *field(&mut value.clone()),
                        onchange: move |e| {
                            let mut next = value;
                            *field(&mut next) = e.checked();
                            onchange(next);
                        },
                    }
                    "{label}"
                }
            }
        }
    }
}
