//! `chopstick import`: upload a `chopstick export` through the API.
//!
//! Safe to rerun: a name the server already holds is reused (the 409 names
//! the existing record), and requirements, dependencies and tags are PUTs.
//! The server gives every record a new id and credits the import's user.

use crate::Error;
use crate::client::Client;
use crate::export::{Export, Recipe, VERSION};
use knife_core::input::{NewIngredient, NewRecipe};
use knife_core::{Classification, ValidName, simplify};
use reqwest::Method;
use serde::Serialize;
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

pub fn read(path: &Path) -> Result<Export, Error> {
    let fail = |reason: String| Error::Export(path.into(), reason);
    let text = std::fs::read_to_string(path).map_err(|e| fail(e.to_string()))?;
    let value: Value = serde_json::from_str(&text).map_err(|e| fail(e.to_string()))?;
    // Checked first, so an older file says so instead of naming a field.
    match value["version"].as_u64() {
        Some(version) if version == u64::from(VERSION) => {}
        Some(version) => return Err(fail(format!("version {version}, expected {VERSION}"))),
        None => {
            return Err(fail(
                "no format version; was it written by `export`?".into(),
            ));
        }
    }
    serde_json::from_value(value).map_err(|e| fail(e.to_string()))
}

/// Check the export against the server's rules and that every reference
/// resolves, so an upload does not stop half way on bad data.
pub fn check(export: &Export) -> Result<Value, Error> {
    let ingredients: BTreeMap<_, _> = export.ingredients.iter().map(|i| (&i.id, i)).collect();
    let recipes: BTreeSet<_> = export.recipes.iter().map(|r| &r.id).collect();
    let mut labels = BTreeSet::new();
    let mut problems = Vec::new();

    for ingredient in &export.ingredients {
        note(
            &mut problems,
            format!("ingredient {:?}", ingredient.name),
            ValidName::new(&ingredient.name).map(drop),
        );
    }
    for label in &export.labels {
        match ValidName::label(label) {
            Ok(valid) => {
                labels.insert(valid.simple_name);
            }
            Err(e) => problems.push(format!("label {label:?}: {e}")),
        }
    }
    for recipe in &export.recipes {
        let what = |detail: &str| format!("recipe {:?}, {detail}", recipe.name);
        note(
            &mut problems,
            what("name"),
            ValidName::new(&recipe.name).map(drop),
        );
        for (id, requirement) in &recipe.requirements {
            let Some(ingredient) = ingredients.get(id) else {
                problems.push(what(&format!("unknown ingredient {id}")));
                continue;
            };
            note(
                &mut problems,
                what(&format!("quantity of {:?}", ingredient.name)),
                requirement.validate(),
            );
        }
        for id in recipe.dependencies.keys() {
            if !recipes.contains(id) {
                problems.push(what(&format!("unknown recipe {id}")));
            }
        }
        for tag in &recipe.tags {
            if !labels.contains(tag) {
                problems.push(what(&format!("unknown label {tag:?}")));
            }
        }
    }

    if !problems.is_empty() {
        return Err(Error::Invalid(problems));
    }

    let count = |f: fn(&Recipe) -> usize| export.recipes.iter().map(f).sum::<usize>();
    Ok(json!({
        "ingredients": export.ingredients.len(),
        "labels": export.labels.len(),
        "recipes": export.recipes.len(),
        "requirements": count(|r| r.requirements.len()),
        "dependencies": count(|r| r.dependencies.len()),
        "tags": count(|r| r.tags.len()),
    }))
}

/// Record a rule violation, if any.
fn note(problems: &mut Vec<String>, what: String, result: Result<(), knife_core::Error>) {
    if let Err(e) = result {
        problems.push(format!("{what}: {e}"));
    }
}

#[derive(Default, Serialize)]
struct Tally {
    created: usize,
    reused: usize,
}

/// Upload the export; returns a report of what happened.
pub fn upload(client: &Client, export: &Export) -> Result<Value, Error> {
    // Exported ids to the server's ids.
    let mut ingredient_ids = BTreeMap::new();
    let mut recipe_ids = BTreeMap::new();
    let mut ingredients = Tally::default();
    let mut recipes = Tally::default();
    let mut flag_conflicts = Vec::new();
    // Tags are PUT by display name, so a new label gets the exported one.
    let labels: BTreeMap<String, &str> = export
        .labels
        .iter()
        .map(|name| (simplify(name), name.as_str()))
        .collect();

    eprintln!("Ingredients ({})", export.ingredients.len());
    for ingredient in &export.ingredients {
        let flags = ingredient.classification;
        let body = NewIngredient {
            name: ingredient.name.clone(),
            dairy: flags.dairy,
            meat: flags.meat,
            gluten: flags.gluten,
            animal_product: flags.animal_product,
        };
        let (id, created) = create_or_reuse(client, "ingredients", &body)?;
        if created {
            ingredients.created += 1;
        } else {
            ingredients.reused += 1;
            // Reused as is: report flags that differ instead of overwriting
            // what someone may have changed since.
            let stored = client.get(&["ingredients", &id], &[])?;
            if classification(&stored) != flags {
                flag_conflicts.push(ingredient.name.clone());
            }
        }
        ingredient_ids.insert(&ingredient.id, id);
    }

    eprintln!("Recipes ({})", export.recipes.len());
    for recipe in &export.recipes {
        let body = NewRecipe {
            name: recipe.name.clone(),
            author: recipe.author.clone(),
            directions: recipe.directions.clone(),
            information: recipe.information.clone(),
        };
        let (id, created) = create_or_reuse(client, "recipes", &body)?;
        if created {
            recipes.created += 1;
        } else {
            recipes.reused += 1;
        }
        recipe_ids.insert(&recipe.id, id);
    }

    let (mut requirements, mut dependencies, mut tags) = (0, 0, 0);
    for (n, recipe) in export.recipes.iter().enumerate() {
        eprintln!("[{}/{}] {}", n + 1, export.recipes.len(), recipe.name);
        let id = &recipe_ids[&recipe.id];

        for (ingredient, requirement) in &recipe.requirements {
            let ingredient = &ingredient_ids[ingredient];
            client.put(&["recipes", id, "requirements", ingredient], requirement)?;
            requirements += 1;
        }
        for (requisite, dependency) in &recipe.dependencies {
            let requisite = &recipe_ids[requisite];
            client.put(&["recipes", id, "dependencies", requisite], dependency)?;
            dependencies += 1;
        }
        for tag in &recipe.tags {
            client.call(
                Method::PUT,
                &["recipes", id, "tags", labels[tag]],
                &[],
                None::<&()>,
            )?;
            tags += 1;
        }
    }

    Ok(json!({
        "ingredients": ingredients,
        "recipes": recipes,
        "requirements": requirements,
        "dependencies": dependencies,
        "tags": tags,
        "ingredients_with_different_flags": flag_conflicts,
    }))
}

/// Create a record, or take the id of the one already holding its name.
fn create_or_reuse(
    client: &Client,
    collection: &str,
    body: &impl Serialize,
) -> Result<(String, bool), Error> {
    let id = |value: &Value| value["id"].as_str().unwrap_or_default().to_owned();
    match client.post(&[collection], body) {
        Ok(created) => Ok((id(&created), true)),
        Err(Error::Api {
            status: 409,
            existing: Some(existing),
            ..
        }) => Ok((id(&existing), false)),
        Err(e) => Err(e),
    }
}

fn classification(record: &Value) -> Classification {
    serde_json::from_value(record["classification"].clone()).unwrap_or_default()
}
