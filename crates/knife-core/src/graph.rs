//! The recipe dependency graph: cycle detection and classification
//! propagation.
//!
//! Storage is async and this crate does no I/O, so callers load the part of
//! the graph an operation needs into a [`Graph`] (inside the same transaction
//! as the write), then ask it what to change.

use crate::{Classification, Error, Recipe, RecipeId};
use std::collections::{BTreeMap, BTreeSet, VecDeque};

/// What the graph needs to know about one recipe.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Node {
    /// Recipes this one depends on.
    pub requisites: BTreeSet<RecipeId>,
    /// Union of this recipe's own ingredients' flags.
    pub own: Classification,
    /// Classification currently stored on the recipe.
    pub stored: Classification,
}

impl From<&Recipe> for Node {
    fn from(recipe: &Recipe) -> Self {
        Self {
            requisites: recipe.dependencies.keys().cloned().collect(),
            own: recipe.own_classification(),
            stored: recipe.classification,
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct Graph {
    nodes: BTreeMap<RecipeId, Node>,
}

impl Graph {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn insert(&mut self, id: RecipeId, node: Node) {
        self.nodes.insert(id, node);
    }

    pub fn get(&self, id: &RecipeId) -> Option<&Node> {
        self.nodes.get(id)
    }

    pub fn get_mut(&mut self, id: &RecipeId) -> Option<&mut Node> {
        self.nodes.get_mut(id)
    }

    pub fn contains(&self, id: &RecipeId) -> bool {
        self.nodes.contains_key(id)
    }

    /// `start` and every recipe it depends on, directly or not. Recipes
    /// missing from the graph are treated as having no requisites.
    pub fn descendants(&self, start: &RecipeId) -> BTreeSet<RecipeId> {
        let mut seen = BTreeSet::from([start.clone()]);
        let mut queue = VecDeque::from([start]);

        while let Some(id) = queue.pop_front() {
            for requisite in self.nodes.get(id).into_iter().flat_map(|n| &n.requisites) {
                if seen.insert(requisite.clone()) {
                    queue.push_back(requisite);
                }
            }
        }

        seen
    }

    /// Check that `recipe` may depend on `requisite`.
    ///
    /// The graph must contain every descendant of `requisite`. Unlike v0.3,
    /// a second path to an existing requisite is allowed: only a real cycle
    /// is refused.
    pub fn check_new_dependency(
        &self,
        recipe: &RecipeId,
        requisite: &RecipeId,
    ) -> Result<(), Error> {
        if recipe == requisite {
            return Err(Error::SelfDependency);
        }
        if self.descendants(requisite).contains(recipe) {
            return Err(Error::DependencyCycle);
        }
        Ok(())
    }

    /// Recompute classifications after a write and return those that changed.
    ///
    /// `changed` lists the recipes whose own ingredients or requisites were
    /// just modified; the graph must already reflect the write. It must
    /// contain every recipe that transitively depends on a `changed` recipe,
    /// and every requisite of those recipes (only `stored` is read for
    /// requisites outside that set).
    pub fn propagate(
        &self,
        changed: &[RecipeId],
    ) -> Result<BTreeMap<RecipeId, Classification>, Error> {
        let mut dependants: BTreeMap<&RecipeId, Vec<&RecipeId>> = BTreeMap::new();
        for (id, node) in &self.nodes {
            for requisite in &node.requisites {
                dependants.entry(requisite).or_default().push(id);
            }
        }

        // Every recipe whose classification may change.
        let mut affected: BTreeSet<&RecipeId> = BTreeSet::new();
        let mut queue: VecDeque<&RecipeId> = VecDeque::new();
        for id in changed {
            let (id, _) = self
                .nodes
                .get_key_value(id)
                .ok_or_else(|| Error::MissingRecipe(id.clone()))?;
            if affected.insert(id) {
                queue.push_back(id);
            }
        }
        while let Some(id) = queue.pop_front() {
            for &dependant in dependants.get(id).into_iter().flatten() {
                if affected.insert(dependant) {
                    queue.push_back(dependant);
                }
            }
        }

        // Visit affected recipes requisites-first (Kahn's algorithm), so each
        // one is computed after everything it depends on.
        let mut pending: BTreeMap<&RecipeId, usize> = affected
            .iter()
            .map(|&id| {
                let count = self.nodes[id]
                    .requisites
                    .iter()
                    .filter(|r| affected.contains(r))
                    .count();
                (id, count)
            })
            .collect();
        let mut ready: VecDeque<&RecipeId> = pending
            .iter()
            .filter(|(_, count)| **count == 0)
            .map(|(&id, _)| id)
            .collect();
        let mut computed: BTreeMap<&RecipeId, Classification> = BTreeMap::new();

        while let Some(id) = ready.pop_front() {
            let node = &self.nodes[id];
            let mut classification = node.own;

            for requisite in &node.requisites {
                classification |= match computed.get(requisite) {
                    Some(c) => *c,
                    None => {
                        self.nodes
                            .get(requisite)
                            .ok_or_else(|| Error::MissingRecipe(requisite.clone()))?
                            .stored
                    }
                };
            }
            computed.insert(id, classification);

            for &dependant in dependants.get(id).into_iter().flatten() {
                if let Some(count) = pending.get_mut(dependant) {
                    *count -= 1;
                    if *count == 0 {
                        ready.push_back(dependant);
                    }
                }
            }
        }

        if computed.len() < affected.len() {
            // Only reachable if stored data already contains a cycle.
            return Err(Error::DependencyCycle);
        }

        Ok(computed
            .into_iter()
            .filter(|(id, c)| self.nodes[*id].stored != *c)
            .map(|(id, c)| (id.clone(), c))
            .collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const MEAT: Classification = Classification {
        dairy: false,
        meat: true,
        gluten: false,
        animal_product: false,
    };
    const DAIRY: Classification = Classification {
        dairy: true,
        meat: false,
        gluten: false,
        animal_product: false,
    };

    fn id(name: &str) -> RecipeId {
        RecipeId::from(name)
    }

    fn node(requisites: &[&str]) -> Node {
        Node {
            requisites: requisites.iter().map(|r| id(r)).collect(),
            ..Default::default()
        }
    }

    /// The v0.3 fixture: fajitas needs guacamole and chipotle chicken,
    /// guacamole needs pico de gallo, horchata stands alone.
    fn fajitas() -> Graph {
        let mut graph = Graph::new();
        graph.insert(id("fajitas"), node(&["guacamole", "chipotle_chicken"]));
        graph.insert(id("guacamole"), node(&["pico_de_gallo"]));
        graph.insert(id("chipotle_chicken"), node(&[]));
        graph.insert(id("pico_de_gallo"), node(&[]));
        graph.insert(id("horchata"), node(&[]));
        graph
    }

    fn ids(names: &[&str]) -> BTreeSet<RecipeId> {
        names.iter().map(|n| id(n)).collect()
    }

    #[test]
    fn descendants_match_v0_3() {
        let graph = fajitas();

        assert_eq!(
            graph.descendants(&id("fajitas")),
            ids(&["fajitas", "guacamole", "pico_de_gallo", "chipotle_chicken"])
        );
        assert_eq!(
            graph.descendants(&id("guacamole")),
            ids(&["guacamole", "pico_de_gallo"])
        );
        assert_eq!(graph.descendants(&id("horchata")), ids(&["horchata"]));
    }

    #[test]
    fn self_dependency_is_refused() {
        let graph = fajitas();
        assert_eq!(
            graph.check_new_dependency(&id("horchata"), &id("horchata")),
            Err(Error::SelfDependency)
        );
    }

    #[test]
    fn cycles_are_refused() {
        let graph = fajitas();
        assert_eq!(
            graph.check_new_dependency(&id("pico_de_gallo"), &id("fajitas")),
            Err(Error::DependencyCycle)
        );
    }

    #[test]
    fn second_path_is_allowed() {
        // v0.3 refused this: pico de gallo is already reachable from fajitas.
        let graph = fajitas();
        assert_eq!(
            graph.check_new_dependency(&id("fajitas"), &id("pico_de_gallo")),
            Ok(())
        );
    }

    #[test]
    fn unrelated_dependency_is_allowed() {
        let graph = fajitas();
        assert_eq!(
            graph.check_new_dependency(&id("horchata"), &id("fajitas")),
            Ok(())
        );
    }

    #[test]
    fn flags_propagate_to_dependants() {
        let mut graph = fajitas();
        graph.get_mut(&id("chipotle_chicken")).unwrap().own = MEAT;

        let changes = graph.propagate(&[id("chipotle_chicken")]).unwrap();

        assert_eq!(
            changes,
            BTreeMap::from([(id("chipotle_chicken"), MEAT), (id("fajitas"), MEAT)])
        );
    }

    #[test]
    fn flags_propagate_through_several_levels() {
        let mut graph = fajitas();
        graph.get_mut(&id("chipotle_chicken")).unwrap().stored = MEAT;
        graph.get_mut(&id("fajitas")).unwrap().stored = MEAT;
        graph.get_mut(&id("pico_de_gallo")).unwrap().own = DAIRY;

        let changes = graph.propagate(&[id("pico_de_gallo")]).unwrap();

        assert_eq!(
            changes,
            BTreeMap::from([
                (id("pico_de_gallo"), DAIRY),
                (id("guacamole"), DAIRY),
                (id("fajitas"), MEAT | DAIRY),
            ])
        );
    }

    #[test]
    fn removing_a_dependency_clears_inherited_flags() {
        let mut graph = fajitas();
        graph.get_mut(&id("chipotle_chicken")).unwrap().own = MEAT;
        graph.get_mut(&id("chipotle_chicken")).unwrap().stored = MEAT;
        graph.get_mut(&id("fajitas")).unwrap().stored = MEAT;

        graph
            .get_mut(&id("fajitas"))
            .unwrap()
            .requisites
            .remove(&id("chipotle_chicken"));
        let changes = graph.propagate(&[id("fajitas")]).unwrap();

        assert_eq!(
            changes,
            BTreeMap::from([(id("fajitas"), Classification::default())])
        );
    }

    #[test]
    fn diamond_is_computed_once_per_recipe() {
        let mut graph = fajitas();
        graph
            .get_mut(&id("fajitas"))
            .unwrap()
            .requisites
            .insert(id("pico_de_gallo"));
        graph.get_mut(&id("pico_de_gallo")).unwrap().own = DAIRY;

        let changes = graph.propagate(&[id("pico_de_gallo")]).unwrap();

        assert_eq!(changes.len(), 3);
        assert_eq!(changes[&id("fajitas")], DAIRY);
    }

    #[test]
    fn unchanged_recipes_are_not_returned() {
        let graph = fajitas();
        assert!(graph.propagate(&[id("guacamole")]).unwrap().is_empty());
    }

    #[test]
    fn missing_requisite_is_an_error() {
        let mut graph = Graph::new();
        graph.insert(id("quiche"), node(&["pate_brisee"]));

        assert_eq!(
            graph.propagate(&[id("quiche")]),
            Err(Error::MissingRecipe(id("pate_brisee")))
        );
    }

    #[test]
    fn missing_changed_recipe_is_an_error() {
        let graph = fajitas();
        assert_eq!(
            graph.propagate(&[id("quiche")]),
            Err(Error::MissingRecipe(id("quiche")))
        );
    }

    #[test]
    fn stored_cycle_is_detected() {
        let mut graph = Graph::new();
        graph.insert(id("a"), node(&["b"]));
        graph.insert(id("b"), node(&["a"]));

        assert_eq!(graph.propagate(&[id("a")]), Err(Error::DependencyCycle));
    }
}
