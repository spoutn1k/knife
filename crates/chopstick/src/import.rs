//! `chopstick import`: upload a v0.3 export through the API.
//!
//! Safe to rerun: a name the server already holds is reused (the 409 names
//! the existing record), and requirements, dependencies and tags are PUTs.

use crate::Error;
use crate::client::Client;
use crate::export::{Export, Recipe};
use knife_core::input::{DependencyInput, NewIngredient, NewRecipe, RequirementInput};
use knife_core::{Classification, ValidName};
use reqwest::Method;
use serde::Serialize;
use serde_json::{Value, json};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

pub fn read(path: &Path) -> Result<Export, Error> {
    let fail = |reason: String| Error::Export(path.into(), reason);
    let text = std::fs::read_to_string(path).map_err(|e| fail(e.to_string()))?;
    serde_json::from_str(&text).map_err(|e| fail(e.to_string()))
}

/// Check the export against the server's rules and that every reference
/// resolves, so an upload does not stop half way on bad data.
pub fn check(export: &Export) -> Result<Value, Error> {
    let ingredients: BTreeSet<&str> = export.ingredients.iter().map(|i| i.id.as_str()).collect();
    let recipes: BTreeSet<&str> = export.recipes.iter().map(|r| r.id.as_str()).collect();
    let mut problems = Vec::new();

    for ingredient in &export.ingredients {
        note(
            &mut problems,
            format!("ingredient {:?}", ingredient.name),
            ValidName::new(&ingredient.name).map(drop),
        );
    }
    for recipe in &export.recipes {
        let what = |detail: &str| format!("recipe {:?}, {detail}", recipe.name);
        note(
            &mut problems,
            what("name"),
            ValidName::new(&recipe.name).map(drop),
        );
        for requirement in &recipe.requirements {
            let ingredient = &requirement.ingredient;
            if !ingredients.contains(ingredient.id.as_str()) {
                problems.push(what(&format!("unknown ingredient {:?}", ingredient.name)));
            }
            note(
                &mut problems,
                what(&format!("quantity of {:?}", ingredient.name)),
                RequirementInput {
                    quantity: requirement.quantity.trim().into(),
                    optional: requirement.optional,
                    group: requirement.group.clone(),
                }
                .validate(),
            );
        }
        for dependency in &recipe.dependencies {
            if !recipes.contains(dependency.recipe.id.as_str()) {
                problems.push(what(&format!(
                    "unknown recipe {:?}",
                    dependency.recipe.name
                )));
            }
        }
        for tag in &recipe.tags {
            note(
                &mut problems,
                what(&format!("label {:?}", tag.name)),
                ValidName::label(&tag.name).map(drop),
            );
        }
    }

    if !problems.is_empty() {
        return Err(Error::Invalid(problems));
    }

    let count = |f: fn(&Recipe) -> usize| export.recipes.iter().map(f).sum::<usize>();
    Ok(json!({
        "ingredients": export.ingredients.len(),
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
    // Old ids to new ids.
    let mut ingredient_ids = BTreeMap::new();
    let mut recipe_ids = BTreeMap::new();
    let mut ingredients = Tally::default();
    let mut recipes = Tally::default();
    let mut flag_conflicts = Vec::new();

    eprintln!("Ingredients ({})", export.ingredients.len());
    for ingredient in &export.ingredients {
        let flags = ingredient.classifications;
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
        ingredient_ids.insert(ingredient.id.as_str(), id);
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
        recipe_ids.insert(recipe.id.as_str(), id);
    }

    let (mut requirements, mut dependencies, mut tags) = (0, 0, 0);
    for (n, recipe) in export.recipes.iter().enumerate() {
        eprintln!("[{}/{}] {}", n + 1, export.recipes.len(), recipe.name);
        let id = &recipe_ids[recipe.id.as_str()];

        for requirement in &recipe.requirements {
            let ingredient = &ingredient_ids[requirement.ingredient.id.as_str()];
            client.put(
                &["recipes", id, "requirements", ingredient],
                &RequirementInput {
                    quantity: requirement.quantity.trim().into(),
                    optional: requirement.optional,
                    group: requirement.group.clone(),
                },
            )?;
            requirements += 1;
        }
        for dependency in &recipe.dependencies {
            let requisite = &recipe_ids[dependency.recipe.id.as_str()];
            client.put(
                &["recipes", id, "dependencies", requisite],
                &DependencyInput {
                    quantity: dependency.quantity.trim().into(),
                    optional: dependency.optional,
                },
            )?;
            dependencies += 1;
        }
        for tag in &recipe.tags {
            client.call(
                Method::PUT,
                &["recipes", id, "tags", &tag.name],
                &[],
                None::<&()>,
            )?;
            tags += 1;
        }
    }

    // The server recomputes classifications from the ingredients; they
    // should match what v0.3 had.
    eprintln!("Checking classifications");
    let mut classification_mismatches = Vec::new();
    for recipe in &export.recipes {
        let stored = client.get(&["recipes", &recipe_ids[recipe.id.as_str()]], &[])?;
        if classification(&stored) != recipe.classifications {
            classification_mismatches.push(recipe.name.clone());
        }
    }

    Ok(json!({
        "ingredients": ingredients,
        "recipes": recipes,
        "requirements": requirements,
        "dependencies": dependencies,
        "tags": tags,
        "ingredients_with_different_flags": flag_conflicts,
        "classification_mismatches": classification_mismatches,
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
