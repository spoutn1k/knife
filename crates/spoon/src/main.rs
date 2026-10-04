//! spoon: the web frontend of knife, a shared family recipe book.
//!
//! A Dioxus app compiled to wasm and served by Firebase Hosting next to the
//! API, which it calls under `/api`. Run it with `just spoon`.

mod api;
mod auth;
mod components;
mod markdown;
mod views;

use api::{Api, use_api};
use auth::{Identity, Session};
use components::{ErrorBanner, Loading};
use dioxus::prelude::*;
use std::collections::BTreeSet;
use std::convert::Infallible;
use std::fmt;
use std::str::FromStr;
use views::{
    EditRecipe, IngredientList, IngredientPage, LabelGraph, LabelList, NewRecipe, NotFound,
    RecipeList, RecipePage, SignIn,
};

pub use api::Error;

const STYLE: Asset = asset!("/assets/main.css");
const ICON: Asset = asset!("/assets/icon.svg");

#[derive(Routable, Clone, PartialEq)]
#[rustfmt::skip]
pub enum Route {
    #[layout(Shell)]
        /// `?labels=a,b` keeps only the recipes with all those labels.
        #[route("/?:labels")]
        RecipeList { labels: LabelSet },
        #[route("/recipes/new")]
        NewRecipe {},
        #[route("/recipes/:id")]
        RecipePage { id: String },
        #[route("/recipes/:id/edit")]
        EditRecipe { id: String },
        #[route("/ingredients")]
        IngredientList {},
        #[route("/ingredients/:id")]
        IngredientPage { id: String },
        #[route("/labels")]
        LabelList {},
        #[route("/labels/graph")]
        LabelGraph {},
        #[route("/:..segments")]
        NotFound { segments: Vec<String> },
}

/// Labels selected on the recipe list, by simple name. In the URL, they are
/// joined by commas.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct LabelSet(pub BTreeSet<String>);

impl LabelSet {
    /// The list filtered by a single label.
    pub fn one(label: &str) -> Self {
        Self(BTreeSet::from([label.to_owned()]))
    }

    /// This selection with `label` added, or removed if it was selected.
    pub fn toggled(&self, label: &str) -> Self {
        let mut labels = self.0.clone();
        if !labels.remove(label) {
            labels.insert(label.to_owned());
        }
        Self(labels)
    }
}

impl FromStr for LabelSet {
    type Err = Infallible;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Ok(Self(
            s.split(',')
                .filter(|l| !l.is_empty())
                .map(String::from)
                .collect(),
        ))
    }
}

impl fmt::Display for LabelSet {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let labels: Vec<&str> = self.0.iter().map(String::as_str).collect();
        f.write_str(&labels.join(","))
    }
}

fn main() {
    dioxus::launch(App);
}

/// Loads the sign-in settings, then provides the [`Api`] to every page.
#[component]
fn App() -> Element {
    let identity = use_resource(|| async {
        let origin = origin();
        Identity::load(&reqwest::Client::new(), origin.as_str()).await
    });

    rsx! {
        document::Stylesheet { href: STYLE }
        document::Link { rel: "icon", href: ICON }
        document::Meta { name: "viewport", content: "width=device-width, initial-scale=1" }
        match &*identity.read() {
            None => rsx! { Loading {} },
            Some(Err(e)) => rsx! {
                main { class: "narrow",
                    ErrorBanner { message: "Cannot load the sign-in settings: {e}" }
                }
            },
            Some(Ok(identity)) => rsx! { Root { identity: identity.clone() } },
        }
    }
}

#[component]
fn Root(identity: Identity) -> Element {
    let session = use_signal(Session::restore);
    use_context_provider(|| Api::new(reqwest::Client::new(), origin(), identity, session));
    rsx! { Router::<Route> {} }
}

/// The page's origin, which also serves the API.
fn origin() -> reqwest::Url {
    let origin = web_sys::window()
        .and_then(|w| w.location().origin().ok())
        .expect("running in a browser");
    reqwest::Url::parse(&origin).expect("the page origin is a URL")
}

/// Header and navigation around every page, or the sign-in form.
#[component]
fn Shell() -> Element {
    let api = use_api();
    let session = api.session;

    let Some(email) = session.read().as_ref().map(|s| s.email.clone()) else {
        return rsx! { SignIn {} };
    };

    // The menu, folded behind a button on phones.
    let mut menu_open = use_signal(|| false);

    rsx! {
        header { class: "top",
            Link {
                class: "brand",
                to: Route::RecipeList { labels: LabelSet::default() },
                onclick: move |_| menu_open.set(false),
                "knife"
            }
            button {
                class: "menu-toggle",
                "aria-label": "Menu",
                "aria-expanded": "{menu_open}",
                "aria-controls": "menu",
                onclick: move |_| menu_open.toggle(),
                MenuIcon { open: menu_open() }
            }
            // Any click in the menu follows a link or signs out: close it.
            div {
                id: "menu",
                class: if menu_open() { "menu open" } else { "menu" },
                onclick: move |_| menu_open.set(false),
                nav {
                    Link { to: Route::IngredientList {}, active_class: "active", "Ingredients" }
                    Link { to: Route::LabelList {}, active_class: "active", "Labels" }
                }
                button { class: "link", onclick: move |_| api.sign_out(), "Sign out" }
            }
        }
        main {
            Membership { key: "{email}" }
            Outlet::<Route> {}
        }
    }
}

/// Three bars, or a cross while the menu is open.
#[component]
fn MenuIcon(open: bool) -> Element {
    rsx! {
        svg {
            class: "icon",
            "aria-hidden": "true",
            view_box: "0 0 24 24",
            fill: "none",
            stroke: "currentColor",
            stroke_width: "2",
            stroke_linecap: "round",
            if open {
                path { d: "M6 6 18 18M18 6 6 18" }
            } else {
                path { d: "M4 7h16M4 12h16M4 17h16" }
            }
        }
    }
}

/// Warns when the signed-in account is not part of the recipe book, which
/// otherwise shows up as an error on every page.
#[component]
fn Membership() -> Element {
    let api = use_api();
    let me = use_resource(move || {
        let api = api.clone();
        async move { api.me().await }
    });

    match &*me.read() {
        Some(Err(e)) if e.status() == Some(403) => rsx! {
            ErrorBanner {
                message: "This account is not a member of the recipe book. Ask a member to add it."
            }
        },
        _ => rsx! {},
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn label_sets_round_trip() {
        let labels: LabelSet = "french,dessert".parse().unwrap();
        assert_eq!(labels.0.len(), 2);
        assert_eq!(labels.to_string(), "dessert,french");
        assert_eq!("".parse::<LabelSet>().unwrap(), LabelSet::default());
        assert_eq!(
            ",french,".parse::<LabelSet>().unwrap(),
            LabelSet::one("french")
        );
    }

    #[test]
    fn toggling_adds_then_removes() {
        let labels = LabelSet::one("french").toggled("dessert");
        assert_eq!(labels.to_string(), "dessert,french");
        assert_eq!(labels.toggled("dessert"), LabelSet::one("french"));
    }
}
