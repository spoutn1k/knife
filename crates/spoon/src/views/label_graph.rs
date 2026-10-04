//! The labels as a graph, drawn the way Obsidian draws notes: a node per
//! label, sized by its recipes, and an edge between two labels found on the
//! same recipes, thicker the more recipes they share. A force simulation lays
//! it out when the page loads, and runs again while a label is dragged, so the
//! rest of the graph follows.

use crate::Error;
use crate::api::use_api;
use crate::components::{ErrorBanner, Loading};
use crate::{LabelSet, Route};
use dioxus::html::input_data::MouseButton;
use dioxus::prelude::*;
use knife_core::{Label, RecipeListing};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::f64::consts::PI;
use web_sys::wasm_bindgen::JsCast;

#[component]
pub fn LabelGraph() -> Element {
    let api = use_api();
    let graph = use_resource(move || {
        let api = api.clone();
        async move {
            let labels = api.labels("").await?;
            let recipes = api.recipes("").await?;
            Ok::<_, Error>(Graph::new(&labels, &recipes))
        }
    });

    rsx! {
        div { class: "title-row",
            h1 { "Label graph" }
            Link { class: "button secondary", to: Route::LabelList {}, "List" }
        }
        p { class: "muted",
            "Labels found on the same recipes are linked. Point at a label to see its "
            "neighbours, drag it to move it, click it to see its recipes."
        }
        match &*graph.read() {
            None => rsx! { Loading {} },
            Some(Err(e)) => rsx! { ErrorBanner { message: e.to_string() } },
            Some(Ok(graph)) if graph.nodes.is_empty() => rsx! { p { class: "muted", "No labels yet." } },
            Some(Ok(graph)) => rsx! { GraphView { graph: graph.clone() } },
        }
    }
}

/// A label held under the pointer.
#[derive(Clone, Copy)]
struct Drag {
    node: usize,
    pointer: i32,
    /// Where the pointer went down, in client pixels.
    from: (f64, f64),
    /// Whether it has moved far enough from there to be a drag, not a click.
    moved: bool,
}

/// How far, in client pixels, the pointer moves before a click is a drag.
const DRAG_THRESHOLD: f64 = 4.0;

#[component]
fn GraphView(graph: Graph) -> Element {
    let navigator = navigator();
    let mut layout = use_signal(|| graph.layout.clone());
    // The label under the pointer, lit with its neighbours.
    let mut hovered = use_signal(|| None);
    let mut drag = use_signal(|| None::<Drag>);
    let mut svg = use_signal(|| None::<web_sys::Element>);
    let mut running = use_signal(|| false);

    // Steps the layout once a frame until it settles, kept warm while a label
    // is dragged.
    let animate = use_callback({
        let edges = graph.edges.clone();
        move |()| {
            if running() {
                return;
            }
            running.set(true);
            let edges = edges.clone();
            spawn(async move {
                loop {
                    next_frame().await;
                    let mut layout = layout.write();
                    if drag.peek().is_some() {
                        layout.reheat();
                    }
                    layout.step(&edges);
                    if layout.settled() {
                        break;
                    }
                }
                running.set(false);
            });
        }
    });

    // Lets go of the dragged label, and says whether it was a click.
    let mut release = move |pointer: i32| {
        let released = (*drag.peek()).filter(|d| d.pointer == pointer)?;
        drag.set(None);
        layout.write().pinned = None;
        Some(released).filter(|d| !d.moved)
    };

    // With a label hovered or dragged, it and its neighbours are lit and the
    // rest dimmed.
    let focus = drag().map(|d| d.node).or(hovered());
    let lit = focus.map(|i| {
        let mut lit = graph.neighbours(i);
        lit.insert(i);
        lit
    });
    let node_class = |i: usize| match &lit {
        None => "node",
        Some(lit) if lit.contains(&i) => "node lit",
        Some(_) => "node dim",
    };
    let edge_class = |e: &Edge| match focus {
        None => "",
        Some(i) if e.a == i || e.b == i => "lit",
        Some(_) => "dim",
    };
    let pos = &layout.read().pos;

    rsx! {
        svg {
            class: if drag().is_some_and(|d| d.moved) { "label-graph dragging" } else { "label-graph" },
            // Fixed to the settled layout, so that the graph does not slide
            // under the pointer as it moves.
            view_box: graph.view_box(),
            role: "img",
            "aria-label": "Labels linked by the recipes they share",
            onmounted: move |e| svg.set(e.data().downcast::<web_sys::Element>().cloned()),
            onpointermove: move |e| {
                let Some(mut d) = *drag.peek() else { return };
                if d.pointer != e.pointer_id() {
                    return;
                }
                let client = e.client_coordinates();
                if !d.moved && (client.x - d.from.0).hypot(client.y - d.from.1) < DRAG_THRESHOLD {
                    return;
                }
                let Some(point) = svg.peek().as_ref().and_then(|s| svg_point(s, client.x, client.y)) else {
                    return;
                };
                if !d.moved {
                    d.moved = true;
                    drag.set(Some(d));
                }
                layout.write().pos[d.node] = point;
                animate(());
            },
            onpointerup: move |e| {
                if let Some(d) = release(e.pointer_id()) {
                    let simple_name = &graph.nodes[d.node].label.simple_name;
                    navigator.push(Route::RecipeList { labels: LabelSet::one(simple_name) });
                }
            },
            onpointercancel: move |e| {
                release(e.pointer_id());
            },
            g {
                for e in &graph.edges {
                    line {
                        key: "{e.a}-{e.b}",
                        class: edge_class(e),
                        x1: "{pos[e.a].0}",
                        y1: "{pos[e.a].1}",
                        x2: "{pos[e.b].0}",
                        y2: "{pos[e.b].1}",
                        stroke_width: "{e.width()}",
                    }
                }
            }
            for (i, (node, &(x, y))) in graph.nodes.iter().zip(pos).enumerate() {
                g {
                    key: "{node.label.simple_name}",
                    class: node_class(i),
                    onpointerenter: move |_| hovered.set(Some(i)),
                    onpointerleave: move |_| hovered.set(None),
                    onpointerdown: move |e| {
                        if e.trigger_button() != Some(MouseButton::Primary) && e.pointer_type() == "mouse" {
                            return;
                        }
                        e.prevent_default();
                        // Keep the pointer's events coming to the graph when
                        // it leaves the label, or the graph.
                        if let Some(svg) = svg.peek().as_ref() {
                            let _ = svg.set_pointer_capture(e.pointer_id());
                        }
                        let client = e.client_coordinates();
                        drag.set(Some(Drag {
                            node: i,
                            pointer: e.pointer_id(),
                            from: (client.x, client.y),
                            moved: false,
                        }));
                        layout.write().pinned = Some(i);
                    },
                    title { "{node.label.name}: {node.label.recipe_count} recipe(s)" }
                    circle { cx: "{x}", cy: "{y}", r: "{node.r}" }
                    text { x: "{x}", y: "{y + node.r + 12.0}", "{node.label.name}" }
                }
            }
        }
    }
}

/// A point in client pixels, in the units of `svg`'s view box.
fn svg_point(svg: &web_sys::Element, x: f64, y: f64) -> Option<(f64, f64)> {
    let screen = svg
        .dyn_ref::<web_sys::SvgGraphicsElement>()?
        .get_screen_ctm()?
        .inverse()
        .ok()?;
    let [a, b, c, d, e, f] = [
        screen.a(),
        screen.b(),
        screen.c(),
        screen.d(),
        screen.e(),
        screen.f(),
    ]
    .map(f64::from);
    Some((a * x + c * y + e, b * x + d * y + f))
}

/// Resolves on the browser's next animation frame.
async fn next_frame() {
    let frame = js_sys::Promise::new(&mut |resolve, _| {
        let requested = web_sys::window().map(|w| w.request_animation_frame(&resolve));
        if !matches!(requested, Some(Ok(_))) {
            let _ = resolve.call0(&resolve);
        }
    });
    let _ = wasm_bindgen_futures::JsFuture::from(frame).await;
}

/// Ideal length of an edge, in SVG units.
const SPACING: f64 = 120.0;
/// How much of the force on a label moves it in a step, relative to how
/// stiffly it is held.
const GAIN: f64 = 0.5;
/// How much of its temperature the layout keeps after each step.
const COOLING: f64 = 0.985;
/// The temperature under which the layout stops moving.
const SETTLED: f64 = 0.5;
/// The temperature the layout is kept at while a label is dragged.
const REHEATED: f64 = SPACING / 8.0;
/// How strongly every label is pulled to the centre, so that lone labels and
/// small clusters stay in sight instead of being pushed to the edges. Like the
/// other forces, its pull grows with distance in SVG units, so changing
/// [`SPACING`] scales the whole layout without changing its shape.
const GRAVITY: f64 = 4.0;

#[derive(Debug, Clone, PartialEq)]
struct Graph {
    nodes: Vec<Node>,
    edges: Vec<Edge>,
    /// Where the simulation settled.
    layout: Layout,
}

#[derive(Debug, Clone, PartialEq)]
struct Node {
    label: Label,
    r: f64,
}

/// Two labels, by index in [`Graph::nodes`], found together on `shared`
/// recipes.
#[derive(Debug, Clone, PartialEq)]
struct Edge {
    a: usize,
    b: usize,
    shared: u32,
}

impl Edge {
    fn width(&self) -> f64 {
        0.5 + f64::from(self.shared).sqrt()
    }
}

impl Graph {
    fn new(labels: &[Label], recipes: &[RecipeListing]) -> Self {
        let edges = colocations(labels, recipes);
        let mut layout = Layout::new(labels.len());
        layout.settle(&edges);
        let nodes = labels
            .iter()
            .map(|label| Node {
                r: 4.0 + 2.5 * f64::from(label.recipe_count).sqrt(),
                label: label.clone(),
            })
            .collect();
        Self {
            nodes,
            edges,
            layout,
        }
    }

    fn neighbours(&self, i: usize) -> BTreeSet<usize> {
        self.edges
            .iter()
            .filter_map(|e| match (e.a == i, e.b == i) {
                (true, _) => Some(e.b),
                (_, true) => Some(e.a),
                _ => None,
            })
            .collect()
    }

    /// The box around every node, with room for the names under them.
    fn view_box(&self) -> String {
        let (mut left, mut top) = (f64::INFINITY, f64::INFINITY);
        let (mut right, mut bottom) = (f64::NEG_INFINITY, f64::NEG_INFINITY);
        for (n, &(x, y)) in self.nodes.iter().zip(&self.layout.pos) {
            left = left.min(x - n.r);
            right = right.max(x + n.r);
            top = top.min(y - n.r);
            bottom = bottom.max(y + n.r);
        }
        // Names are centred under their node and are wider than it.
        let (pad_x, pad_y) = (70.0, 25.0);
        format!(
            "{} {} {} {}",
            left - pad_x,
            top - pad_y,
            right - left + 2.0 * pad_x,
            bottom - top + 2.0 * pad_y
        )
    }
}

/// An edge for every pair of labels found on the same recipe. Tags with no
/// label in `labels` are ignored.
fn colocations(labels: &[Label], recipes: &[RecipeListing]) -> Vec<Edge> {
    let index: HashMap<&str, usize> = labels
        .iter()
        .enumerate()
        .map(|(i, l)| (l.simple_name.as_str(), i))
        .collect();
    let mut shared: BTreeMap<(usize, usize), u32> = BTreeMap::new();
    for recipe in recipes {
        let mut tags: Vec<usize> = recipe
            .tags
            .iter()
            .filter_map(|t| index.get(t.as_str()).copied())
            .collect();
        tags.sort_unstable();
        for (i, &a) in tags.iter().enumerate() {
            for &b in &tags[i + 1..] {
                *shared.entry((a, b)).or_default() += 1;
            }
        }
    }
    shared
        .into_iter()
        .map(|((a, b), shared)| Edge { a, b, shared })
        .collect()
}

/// Positions of the labels, moved a step at a time by Fruchterman–Reingold
/// forces: every pair of labels repels, edges pull their ends together, and
/// everything is pulled to the centre. Steps shrink as the layout cools, until
/// it settles. Quadratic in the labels, which is fine for the few hundred of
/// a recipe book.
#[derive(Debug, Clone, PartialEq)]
struct Layout {
    pos: Vec<(f64, f64)>,
    /// Largest move of a step.
    temperature: f64,
    /// The label held under the pointer, which the forces do not move.
    pinned: Option<usize>,
}

impl Layout {
    /// `n` labels on a sunflower spiral: spread evenly, and the same on every
    /// load, so the settled layout is too.
    fn new(n: usize) -> Self {
        let golden_angle = PI * (3.0 - 5f64.sqrt());
        let pos = (0..n)
            .map(|i| {
                let r = SPACING * 0.5 * (i as f64 + 0.5).sqrt();
                let a = i as f64 * golden_angle;
                (r * a.cos(), r * a.sin())
            })
            .collect();
        Self {
            pos,
            temperature: SPACING,
            pinned: None,
        }
    }

    fn settled(&self) -> bool {
        self.temperature < SETTLED
    }

    fn settle(&mut self, edges: &[Edge]) {
        while !self.settled() {
            self.step(edges);
        }
    }

    /// Warm the layout up, so that it rearranges around a dragged label.
    fn reheat(&mut self) {
        self.temperature = self.temperature.max(REHEATED);
    }

    fn step(&mut self, edges: &[Edge]) {
        let pos = &mut self.pos;
        let n = pos.len();
        let mut force = vec![(0.0, 0.0); n];
        // How hard each label is held in place: a fraction of its force is
        // as far as it can move without overshooting and shaking.
        let mut stiffness = vec![GRAVITY; n];
        for i in 0..n {
            for j in i + 1..n {
                let (dx, dy) = (pos[i].0 - pos[j].0, pos[i].1 - pos[j].1);
                // k²/d along the unit vector (dx, dy) / d.
                let f = SPACING * SPACING / (dx * dx + dy * dy).max(0.01);
                force[i].0 += dx * f;
                force[i].1 += dy * f;
                force[j].0 -= dx * f;
                force[j].1 -= dy * f;
            }
        }
        for e in edges {
            let (dx, dy) = (pos[e.a].0 - pos[e.b].0, pos[e.a].1 - pos[e.b].1);
            // d²/k along the unit vector, stronger for labels sharing more.
            let weight = 1.0 + f64::from(e.shared).ln();
            let f = (dx * dx + dy * dy).sqrt() / SPACING * weight;
            stiffness[e.a] += 2.0 * weight;
            stiffness[e.b] += 2.0 * weight;
            force[e.a].0 -= dx * f;
            force[e.a].1 -= dy * f;
            force[e.b].0 += dx * f;
            force[e.b].1 += dy * f;
        }

        for (i, ((x, y), (fx, fy))) in pos.iter_mut().zip(force).enumerate() {
            let gain = GAIN / stiffness[i];
            if self.pinned == Some(i) {
                continue;
            }
            let (fx, fy) = (fx - *x * GRAVITY, fy - *y * GRAVITY);
            let len = (fx * fx + fy * fy).sqrt();
            if len > 0.0 {
                let moved = (len * gain).min(self.temperature);
                *x += fx / len * moved;
                *y += fy / len * moved;
            }
        }
        self.temperature *= COOLING;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use knife_core::{Classification, RecipeId};

    fn label(name: &str) -> Label {
        Label {
            simple_name: name.to_owned(),
            name: name.to_owned(),
            recipe_count: 1,
        }
    }

    fn recipe(tags: &[&str]) -> RecipeListing {
        RecipeListing {
            id: RecipeId::from("r"),
            name: "r".to_owned(),
            author: String::new(),
            tags: tags.iter().map(|&t| t.to_owned()).collect(),
            classification: Classification::default(),
        }
    }

    #[test]
    fn labels_on_the_same_recipes_are_linked() {
        let labels = ["dessert", "french", "quick", "lonely"].map(label);
        let recipes = [
            recipe(&["french", "dessert"]),
            recipe(&["dessert", "french", "quick"]),
            recipe(&["lonely", "unknown"]),
        ];
        let edges = colocations(&labels, &recipes);
        assert_eq!(
            edges,
            [
                Edge {
                    a: 0,
                    b: 1,
                    shared: 2
                },
                Edge {
                    a: 0,
                    b: 2,
                    shared: 1
                },
                Edge {
                    a: 1,
                    b: 2,
                    shared: 1
                },
            ]
        );
    }

    #[test]
    fn linked_labels_end_up_closer() {
        // Two triangles, and a label linked to nothing.
        let edge = |a, b| Edge { a, b, shared: 1 };
        let edges = [
            edge(0, 1),
            edge(1, 2),
            edge(0, 2),
            edge(3, 4),
            edge(4, 5),
            edge(3, 5),
        ];
        let mut layout = Layout::new(7);
        layout.settle(&edges);
        let pos = layout.pos;
        let dist = |i: usize, j: usize| {
            ((pos[i].0 - pos[j].0).powi(2) + (pos[i].1 - pos[j].1).powi(2)).sqrt()
        };

        assert!(pos.iter().all(|(x, y)| x.is_finite() && y.is_finite()));
        let within = dist(0, 1).max(dist(3, 4));
        let across = dist(0, 3).min(dist(2, 5));
        assert!(within < across, "{within} vs {across}");
        // The lone label is kept in sight.
        assert!(dist(6, 0) < 10.0 * SPACING);
    }
}
