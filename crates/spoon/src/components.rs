//! Pieces shared by several pages.

use crate::Error;
use dioxus::prelude::*;
use knife_core::Classification;
use nucleo_matcher::pattern::{CaseMatching, Normalization, Pattern};
use nucleo_matcher::{Config, Matcher, Utf32Str};
use std::cmp::Ordering;
use std::future::Future;
use std::rc::Rc;
use unicode_segmentation::UnicodeSegmentation;
use wasm_bindgen::JsCast;
use wasm_bindgen::closure::Closure;

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

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum Diet {
    Vegan,
    Vegetarian,
    DairyFree,
    GlutenFree,
}

impl Diet {
    pub const ALL: [Self; 4] = [
        Self::Vegan,
        Self::Vegetarian,
        Self::DairyFree,
        Self::GlutenFree,
    ];

    /// Whether a recipe so classified fits this diet. Vegan recipes fit the
    /// vegetarian diet too.
    pub fn allows(self, c: Classification) -> bool {
        match self {
            Self::Vegan => !c.meat && !c.dairy && !c.animal_product,
            Self::Vegetarian => !c.meat,
            Self::DairyFree => !c.dairy,
            Self::GlutenFree => !c.gluten,
        }
    }

    /// The diets a classification allows. Vegan implies vegetarian, so only
    /// the stronger of the two is listed.
    pub fn of(c: Classification) -> Vec<Self> {
        let vegan = Self::Vegan.allows(c);
        Self::ALL
            .into_iter()
            .filter(|diet| diet.allows(c) && !(vegan && *diet == Self::Vegetarian))
            .collect()
    }

    /// The diet's name in URLs.
    pub fn slug(self) -> &'static str {
        match self {
            Self::Vegan => "vegan",
            Self::Vegetarian => "vegetarian",
            Self::DairyFree => "dairy-free",
            Self::GlutenFree => "gluten-free",
        }
    }

    pub fn from_slug(slug: &str) -> Option<Self> {
        Self::ALL.into_iter().find(|d| d.slug() == slug)
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

/// Two paths joining, for merge buttons shown as icons.
#[component]
pub fn MergeIcon() -> Element {
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
            circle { cx: "6", cy: "5", r: "2" }
            circle { cx: "6", cy: "19", r: "2" }
            circle { cx: "18", cy: "12", r: "2" }
            path { d: "M6 7v10" }
            path { d: "M6 7c0 3 3 5 10 5" }
        }
    }
}

/// A key, for password buttons shown as icons.
#[component]
pub fn KeyIcon() -> Element {
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
            circle { cx: "8", cy: "15", r: "4" }
            path { d: "M10.8 12.2 20 3" }
            path { d: "M16 7l3 3" }
            path { d: "M18 5l2 2" }
        }
    }
}

/// A bin, for delete buttons shown as icons.
#[component]
pub fn TrashIcon() -> Element {
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
            path { d: "M4 7h16" }
            path { d: "M9 7V4h6v3" }
            path { d: "M6 7l1 13h10l1-13" }
            path { d: "M10 11v5M14 11v5" }
        }
    }
}

/// A label's hue in degrees, always the same for the same label. The color
/// scheme picks the lightness and saturation; see `.tinted` in the stylesheet.
pub fn hue(simple_name: &str) -> u32 {
    fnv(0, simple_name) % 360
}

/// FNV-1a of `seed` then `text`: stable across builds, unlike the standard
/// hasher.
pub fn fnv(seed: u32, text: &str) -> u32 {
    seed.to_le_bytes()
        .into_iter()
        .chain(text.bytes())
        .fold(0x811c_9dc5, |h, b| {
            (h ^ u32::from(b)).wrapping_mul(0x0100_0193)
        })
}

/// The style giving a `.tinted` element its label's color.
pub fn tint(simple_name: &str) -> String {
    format!("--hue: {}", hue(simple_name))
}

/// An item kept by [`fuzzy_filter`], with the positions of the characters
/// of its name that matched, for [`Highlight`].
#[derive(Debug, Clone, PartialEq)]
pub struct Match<T> {
    pub item: T,
    /// Grapheme positions, sorted.
    pub indices: Vec<u32>,
}

/// The `items` whose name matches `search` as fzf would match it, best
/// match first; ties keep their order in `items`.
///
/// Each word of `search` must match, in any order, as letters appearing in
/// that order: "trt pom" finds "Tarte aux pommes". Case and accents are
/// ignored, and fzf's operators work: `^tar` starts with, `'pom` contains
/// exactly, `!choc` excludes.
pub fn fuzzy_filter<T: Clone>(
    items: &[T],
    name: impl Fn(&T) -> &str,
    search: &str,
) -> Vec<Match<T>> {
    let pattern = Pattern::parse(search, CaseMatching::Ignore, Normalization::Smart);
    let mut matcher = Matcher::new(Config::DEFAULT);
    let mut chars = Vec::new();
    let mut indices = Vec::new();
    let mut scored: Vec<(u32, Match<T>)> = items
        .iter()
        .filter_map(|item| {
            let name = name(item);
            // One char per grapheme, as `Highlight` counts them. Unlike
            // `Utf32Str::new`, never falls back to bytes for non-ASCII text.
            let haystack = if name.is_ascii() {
                Utf32Str::Ascii(name.as_bytes())
            } else {
                chars.clear();
                chars.extend(nucleo_matcher::chars::graphemes(name));
                Utf32Str::Unicode(&chars)
            };
            indices.clear();
            let score = pattern.indices(haystack, &mut matcher, &mut indices)?;
            // Each word's positions are appended separately.
            let mut matched = indices.clone();
            matched.sort_unstable();
            matched.dedup();
            let item = item.clone();
            Some((
                score,
                Match {
                    item,
                    indices: matched,
                },
            ))
        })
        .collect();
    // Stable, so equal scores stay in the given order.
    scored.sort_by_key(|(score, _)| std::cmp::Reverse(*score));
    scored.into_iter().map(|(_, m)| m).collect()
}

/// `text` with the graphemes at `indices`, as a [`Match`] gives them, marked.
#[component]
pub fn Highlight(text: String, indices: Vec<u32>) -> Element {
    // Runs of matched and unmatched text.
    let mut runs: Vec<(String, bool)> = Vec::new();
    for (i, grapheme) in text.graphemes(true).enumerate() {
        let hit = indices.binary_search(&(i as u32)).is_ok();
        match runs.last_mut() {
            Some((run, was_hit)) if *was_hit == hit => run.push_str(grapheme),
            _ => runs.push((grapheme.to_owned(), hit)),
        }
    }
    rsx! {
        for (run, hit) in runs {
            if hit {
                mark { class: "match", "{run}" }
            } else {
                "{run}"
            }
        }
    }
}

/// A search field, filtering a list as it is typed. Pressing "/" anywhere
/// but in another field focuses it.
/// A column a table of `Item`s can be sorted by.
pub trait SortColumn: Copy + PartialEq + 'static {
    type Item;

    /// Compares two items on this column, ascending.
    fn compare(self, a: &Self::Item, b: &Self::Item) -> Ordering;

    /// Whether the first sort is descending: counts read best largest first,
    /// text A to Z.
    fn starts_descending(self) -> bool;
}

/// The column a table is sorted by, and whether descending. Unsorted, rows
/// keep the given order, such as best match first.
pub type Sort<C> = Option<(C, bool)>;

/// Sorts `rows` as `sort` says. Stable, so ties keep the given order.
pub fn sort_rows<C: SortColumn>(rows: &mut [Match<C::Item>], sort: Sort<C>) {
    if let Some((column, descending)) = sort {
        rows.sort_by(|a, b| {
            let order = column.compare(&a.item, &b.item);
            if descending { order.reverse() } else { order }
        });
    }
}

/// A column heading that sorts the table by its column. Selecting it again
/// reverses the order, then a third time goes back to the given order.
#[component]
pub fn SortHeader<C: SortColumn>(
    column: C,
    sort: Signal<Sort<C>>,
    #[props(default)] class: String,
    children: Element,
) -> Element {
    let current = sort().filter(|(c, _)| *c == column).map(|(_, d)| d);
    let first = column.starts_descending();
    let (aria, arrow) = match current {
        None => ("none", ""),
        Some(true) => ("descending", "▾"),
        Some(false) => ("ascending", "▴"),
    };

    rsx! {
        th { class: "{class}", "aria-sort": aria,
            button {
                class: "sort",
                r#type: "button",
                onclick: move |_| {
                    sort.set(match current {
                        None => Some((column, first)),
                        Some(d) if d == first => Some((column, !first)),
                        Some(_) => None,
                    })
                },
                {children}
                span { class: "arrow", "aria-hidden": "true", "{arrow}" }
            }
        }
    }
}

#[component]
pub fn SearchBox(value: Signal<String>, placeholder: String) -> Element {
    use_slash_focus();
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

/// Listens, while the calling component is mounted, for "/" pressed outside
/// a text field, and focuses the page's search field instead of typing it.
fn use_slash_focus() {
    let listener = use_hook(|| {
        let listener =
            Closure::<dyn Fn(web_sys::KeyboardEvent)>::new(|e: web_sys::KeyboardEvent| {
                if e.key() != "/" || e.ctrl_key() || e.meta_key() || e.alt_key() {
                    return;
                }
                let Some(document) = web_sys::window().and_then(|w| w.document()) else {
                    return;
                };
                if document.active_element().is_some_and(|el| is_editable(&el)) {
                    return;
                }
                let search = document
                    .query_selector("input.search")
                    .ok()
                    .flatten()
                    .and_then(|el| el.dyn_into::<web_sys::HtmlElement>().ok());
                if let Some(search) = search {
                    e.prevent_default();
                    let _ = search.focus();
                }
            });
        if let Some(document) = web_sys::window().and_then(|w| w.document()) {
            let _ = document
                .add_event_listener_with_callback("keydown", listener.as_ref().unchecked_ref());
        }
        Rc::new(listener)
    });
    use_drop(move || {
        if let Some(document) = web_sys::window().and_then(|w| w.document()) {
            let _ = document.remove_event_listener_with_callback(
                "keydown",
                listener.as_ref().as_ref().unchecked_ref(),
            );
        }
    });
}

/// Whether typing in `el` enters text, so "/" must reach it.
fn is_editable(el: &web_sys::Element) -> bool {
    matches!(el.tag_name().as_str(), "INPUT" | "TEXTAREA" | "SELECT")
        || el
            .dyn_ref::<web_sys::HtmlElement>()
            .is_some_and(|el| el.is_content_editable())
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

#[cfg(test)]
mod tests {
    use super::{fuzzy_filter, hue};

    #[test]
    fn hues_are_stable_and_in_range() {
        assert_eq!(hue("dessert"), hue("dessert"));
        for name in ["dessert", "soup", "weeknight", "breakfast", ""] {
            assert!(hue(name) < 360);
        }
    }

    fn search(query: &str) -> Vec<&'static str> {
        let names = [
            "Crème brûlée",
            "Pâte brisée",
            "Tarte aux pommes",
            "Tarte tatin",
            "Compote de pommes",
        ];
        fuzzy_filter(&names, |n| n, query)
            .into_iter()
            .map(|m| m.item)
            .collect()
    }

    #[test]
    fn empty_search_keeps_everything_in_order() {
        assert_eq!(search("").len(), 5);
        assert_eq!(search("  ")[0], "Crème brûlée");
    }

    #[test]
    fn letters_in_order_and_words_in_any_order() {
        assert_eq!(search("trt pom"), ["Tarte aux pommes"]);
        assert_eq!(search("pommes tarte"), ["Tarte aux pommes"]);
    }

    #[test]
    fn case_and_accents_are_ignored() {
        assert_eq!(search("CREME"), ["Crème brûlée"]);
        assert_eq!(search("pate"), ["Pâte brisée"]);
    }

    #[test]
    fn better_matches_come_first() {
        assert_eq!(
            search("pommes")[..2],
            ["Tarte aux pommes", "Compote de pommes"]
        );
        assert_eq!(search("tatin")[0], "Tarte tatin");
    }

    #[test]
    fn fzf_operators_work() {
        assert_eq!(search("^tarte !tatin"), ["Tarte aux pommes"]);
    }

    #[test]
    fn matched_positions_count_graphemes() {
        let names = ["Crème brûlée"];
        let found = fuzzy_filter(&names, |n| n, "brule");
        // "b r û l é" are graphemes 6 to 10, after "Crème ".
        assert_eq!(found[0].indices, [6, 7, 8, 9, 10]);
    }
}
