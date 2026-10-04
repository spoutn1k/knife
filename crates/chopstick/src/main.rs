//! chopstick: a command-line client for the knife recipe server.
//!
//! `chopstick login` once, then one subcommand per API endpoint. Responses
//! are printed as JSON, for reading or for `jq`.

mod client;
mod credentials;
mod export;
mod import;

use clap::{Args, Parser, Subcommand};
use client::Client;
use credentials::Credentials;
use knife_core::input::{
    DependencyInput, IngredientPatch, LabelPatch, NewIngredient, NewRecipe, RecipePatch,
    RequirementInput,
};
use reqwest::Method;
use serde_json::Value;
use std::io::Read;
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("not logged in; run `chopstick login`")]
    NotLoggedIn,
    #[error("cannot find the home directory")]
    NoHome,
    #[error("credentials file {0}: {1}")]
    Credentials(PathBuf, String),
    #[error("could not read the password: {0}")]
    Password(std::io::Error),
    #[error("could not read standard input: {0}")]
    Stdin(std::io::Error),
    #[error("sign-in failed: {0}")]
    SignIn(String),
    #[error("cannot read export {0}: {1}")]
    Export(PathBuf, String),
    #[error("the export breaks the server's rules:\n  {}", .0.join("\n  "))]
    Invalid(Vec<String>),
    #[error("unexpected response from {0}: {1}")]
    Response(String, serde_json::Error),
    #[error("invalid server URL: {0}")]
    Url(String),
    #[error(transparent)]
    Http(#[from] reqwest::Error),
    #[error("{method} {path}: {status} {detail}")]
    Api {
        method: Method,
        path: String,
        status: u16,
        detail: String,
        /// On a 409, the record causing the conflict.
        existing: Option<Value>,
    },
}

#[derive(Parser)]
#[command(version, about)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Sign in and remember the account for later commands
    Login {
        #[arg(long, env = "KNIFE_EMAIL")]
        email: String,
        /// The Firebase project's web API key (Project settings, General)
        #[arg(long, env = "KNIFE_API_KEY")]
        api_key: String,
        #[arg(long, env = "KNIFE_URL", default_value = "https://knife-c51d5.web.app")]
        url: String,
    },
    /// Forget the stored account
    Logout,
    /// Show the signed-in user
    Me,
    /// Ingredients and their dietary flags
    #[command(subcommand)]
    Ingredient(IngredientCommand),
    /// Recipes, with their requirements, dependencies and tags
    #[command(subcommand)]
    Recipe(RecipeCommand),
    /// Labels, which recipes are tagged with
    #[command(subcommand)]
    Label(LabelCommand),
    /// Upload a file written by `export`; safe to rerun
    Import {
        file: PathBuf,
        /// Only check the export, without uploading anything
        #[arg(long)]
        dry_run: bool,
    },
    /// Print every ingredient, label and recipe as JSON, losing nothing
    Export,
}

#[derive(Args)]
struct Search {
    /// Only names starting with this
    #[arg(long, default_value = "")]
    prefix: String,
}

#[derive(Subcommand)]
enum IngredientCommand {
    /// List ingredients
    List(Search),
    /// Show an ingredient and the recipes using it
    Show { id: String },
    /// Create an ingredient
    Create {
        name: String,
        #[arg(long)]
        dairy: bool,
        #[arg(long)]
        meat: bool,
        #[arg(long)]
        gluten: bool,
        #[arg(long)]
        animal_product: bool,
    },
    /// Rename an ingredient or change its flags
    Edit {
        id: String,
        #[arg(long)]
        name: Option<String>,
        #[arg(long)]
        dairy: Option<bool>,
        #[arg(long)]
        meat: Option<bool>,
        #[arg(long)]
        gluten: Option<bool>,
        #[arg(long)]
        animal_product: Option<bool>,
    },
    /// Delete an ingredient no recipe uses
    Delete { id: String },
}

#[derive(Subcommand)]
enum RecipeCommand {
    /// List recipes
    List(Search),
    /// Show a recipe
    Show { id: String },
    /// Create a recipe
    Create {
        name: String,
        /// Where the recipe comes from
        #[arg(long, default_value = "")]
        author: String,
        /// The directions; `-` reads them from standard input
        #[arg(long, default_value = "")]
        directions: String,
        #[arg(long, default_value = "")]
        information: String,
    },
    /// Change a recipe's name, author, directions or information
    Edit {
        id: String,
        #[arg(long)]
        name: Option<String>,
        #[arg(long)]
        author: Option<String>,
        /// The directions; `-` reads them from standard input
        #[arg(long)]
        directions: Option<String>,
        #[arg(long)]
        information: Option<String>,
    },
    /// Delete a recipe no other recipe depends on
    Delete { id: String },
    /// Add an ingredient to a recipe, or replace its quantity and options
    Require {
        recipe: String,
        ingredient: String,
        quantity: String,
        #[arg(long)]
        optional: bool,
        /// Part of the recipe the ingredient belongs to, e.g. "sauce"
        #[arg(long, default_value = "")]
        group: String,
    },
    /// Remove an ingredient from a recipe
    Unrequire { recipe: String, ingredient: String },
    /// Make a recipe use another one, or replace that use's quantity
    Depend {
        recipe: String,
        requisite: String,
        #[arg(long, default_value = "")]
        quantity: String,
        #[arg(long)]
        optional: bool,
    },
    /// Stop a recipe using another one
    Undepend { recipe: String, requisite: String },
    /// Tag a recipe with a label, creating the label if needed
    Tag { recipe: String, label: String },
    /// Remove a label from a recipe
    Untag { recipe: String, label: String },
}

#[derive(Subcommand)]
enum LabelCommand {
    /// List labels
    List(Search),
    /// Show a label and the recipes tagged with it
    Show { label: String },
    /// Rename a label on every recipe
    Rename { label: String, name: String },
    /// Delete a label and remove it from every recipe
    Delete { label: String },
}

fn main() -> ExitCode {
    match run(Cli::parse().command) {
        Ok(Value::Null) => ExitCode::SUCCESS,
        Ok(value) => {
            println!("{value:#}");
            ExitCode::SUCCESS
        }
        Err(err) => {
            eprintln!("chopstick: {err}");
            if let Error::Api {
                existing: Some(existing),
                ..
            } = &err
            {
                eprintln!("{existing:#}");
            }
            ExitCode::FAILURE
        }
    }
}

fn run(command: Command) -> Result<Value, Error> {
    match command {
        Command::Login {
            email,
            api_key,
            url,
        } => {
            let password = match std::env::var("KNIFE_PASSWORD") {
                Ok(password) => password,
                Err(_) => rpassword::prompt_password("Password: ").map_err(Error::Password)?,
            };
            let refresh_token = client::sign_in(&api_key, &email, &password)?;
            let credentials = Credentials {
                url,
                api_key,
                email,
                refresh_token,
            };
            // Check the account works against the server before keeping it.
            let me = Client::new(&credentials)?.get(&["me"], &[])?;
            let path = credentials.save()?;
            eprintln!("Logged in; credentials saved to {}", path.display());
            Ok(me)
        }
        Command::Logout => {
            Credentials::remove()?;
            Ok(Value::Null)
        }
        Command::Import {
            file,
            dry_run: true,
        } => import::check(&import::read(&file)?),
        command => {
            let client = Client::new(&Credentials::load()?)?;
            match command {
                Command::Me => client.get(&["me"], &[]),
                Command::Ingredient(command) => ingredient(&client, command),
                Command::Recipe(command) => recipe(&client, command),
                Command::Label(command) => label(&client, command),
                Command::Import { file, .. } => {
                    let export = import::read(&file)?;
                    import::check(&export)?;
                    import::upload(&client, &export)
                }
                Command::Export => {
                    let export = export::download(&client)?;
                    Ok(serde_json::to_value(export).expect("an export is valid JSON"))
                }
                Command::Login { .. } | Command::Logout => unreachable!("handled above"),
            }
        }
    }
}

fn ingredient(client: &Client, command: IngredientCommand) -> Result<Value, Error> {
    match command {
        IngredientCommand::List(search) => {
            client.get(&["ingredients"], &[("prefix", &search.prefix)])
        }
        IngredientCommand::Show { id } => client.get(&["ingredients", &id], &[]),
        IngredientCommand::Create {
            name,
            dairy,
            meat,
            gluten,
            animal_product,
        } => client.post(
            &["ingredients"],
            &NewIngredient {
                name,
                dairy,
                meat,
                gluten,
                animal_product,
            },
        ),
        IngredientCommand::Edit {
            id,
            name,
            dairy,
            meat,
            gluten,
            animal_product,
        } => client.patch(
            &["ingredients", &id],
            &IngredientPatch {
                name,
                dairy,
                meat,
                gluten,
                animal_product,
            },
        ),
        IngredientCommand::Delete { id } => client.delete(&["ingredients", &id]),
    }
}

fn recipe(client: &Client, command: RecipeCommand) -> Result<Value, Error> {
    match command {
        RecipeCommand::List(search) => client.get(&["recipes"], &[("prefix", &search.prefix)]),
        RecipeCommand::Show { id } => client.get(&["recipes", &id], &[]),
        RecipeCommand::Create {
            name,
            author,
            directions,
            information,
        } => client.post(
            &["recipes"],
            &NewRecipe {
                name,
                author,
                directions: from_stdin_if_dash(directions)?,
                information,
            },
        ),
        RecipeCommand::Edit {
            id,
            name,
            author,
            directions,
            information,
        } => client.patch(
            &["recipes", &id],
            &RecipePatch {
                name,
                author,
                directions: directions.map(from_stdin_if_dash).transpose()?,
                information,
            },
        ),
        RecipeCommand::Delete { id } => client.delete(&["recipes", &id]),
        RecipeCommand::Require {
            recipe,
            ingredient,
            quantity,
            optional,
            group,
        } => client.put(
            &["recipes", &recipe, "requirements", &ingredient],
            &RequirementInput {
                quantity,
                optional,
                group,
            },
        ),
        RecipeCommand::Unrequire { recipe, ingredient } => {
            client.delete(&["recipes", &recipe, "requirements", &ingredient])
        }
        RecipeCommand::Depend {
            recipe,
            requisite,
            quantity,
            optional,
        } => client.put(
            &["recipes", &recipe, "dependencies", &requisite],
            &DependencyInput { quantity, optional },
        ),
        RecipeCommand::Undepend { recipe, requisite } => {
            client.delete(&["recipes", &recipe, "dependencies", &requisite])
        }
        RecipeCommand::Tag { recipe, label } => client.call(
            Method::PUT,
            &["recipes", &recipe, "tags", &label],
            &[],
            None::<&()>,
        ),
        RecipeCommand::Untag { recipe, label } => {
            client.delete(&["recipes", &recipe, "tags", &label])
        }
    }
}

fn label(client: &Client, command: LabelCommand) -> Result<Value, Error> {
    match command {
        LabelCommand::List(search) => client.get(&["labels"], &[("prefix", &search.prefix)]),
        LabelCommand::Show { label } => client.get(&["labels", &label], &[]),
        LabelCommand::Rename { label, name } => {
            client.patch(&["labels", &label], &LabelPatch { name })
        }
        LabelCommand::Delete { label } => client.delete(&["labels", &label]),
    }
}

/// `-` means: read the text from standard input.
fn from_stdin_if_dash(text: String) -> Result<String, Error> {
    if text != "-" {
        return Ok(text);
    }
    let mut input = String::new();
    std::io::stdin()
        .read_to_string(&mut input)
        .map_err(Error::Stdin)?;
    Ok(input)
}
