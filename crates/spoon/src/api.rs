//! Typed calls to the knife API, served from the same origin under `/api`.

use crate::auth::{IdToken, Identity, Session};
use dioxus::prelude::*;
use knife_core::input::{
    DependencyInput, IngredientPatch, LabelPatch, NewIngredient, NewRecipe, RecipePatch,
    RequirementInput,
};
use knife_core::{
    Ingredient, IngredientDetails, IngredientId, Label, Recipe, RecipeId, RecipeListing, Summary,
};
use reqwest::{Method, Url};
use serde::de::DeserializeOwned;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::cell::RefCell;
use std::rc::Rc;

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("{0}")]
    SignIn(String),

    /// The stored refresh token was refused; the user must sign in again.
    #[error("{0}")]
    SessionExpired(String),

    #[error("not signed in")]
    SignedOut,

    #[error("cannot reach the server: {0}")]
    Http(#[from] reqwest::Error),

    #[error("{detail}")]
    Api {
        status: u16,
        detail: String,
        /// On a 409, the record causing the conflict.
        existing: Option<Value>,
    },

    #[error("unexpected response from the server: {0}")]
    Response(#[from] serde_json::Error),

    #[error("there is no recipe named {0:?}")]
    NoSuchRecipe(String),

    #[error("there is no ingredient named {0:?}")]
    NoSuchIngredient(String),

    #[error("there is no label named {0:?}")]
    NoSuchLabel(String),

    #[error("cannot merge into itself")]
    SelfMerge,

    #[error(transparent)]
    Rule(#[from] knife_core::Error),
}

impl Error {
    /// On a conflict, the record already there, such as the recipe holding a
    /// name.
    pub fn existing<T: DeserializeOwned>(&self) -> Option<T> {
        match self {
            Self::Api {
                existing: Some(existing),
                ..
            } => serde_json::from_value(existing.clone()).ok(),
            _ => None,
        }
    }

    pub fn status(&self) -> Option<u16> {
        match self {
            Self::Api { status, .. } => Some(*status),
            _ => None,
        }
    }
}

pub type Result<T, E = Error> = std::result::Result<T, E>;

/// The signed-in user, as `GET /api/me` returns it.
#[derive(Debug, Clone, PartialEq, Deserialize)]
pub struct Me {
    pub uid: String,
    pub email: Option<String>,
}

/// Shared through the Dioxus context; cheap to clone.
#[derive(Clone)]
pub struct Api {
    http: reqwest::Client,
    origin: Url,
    identity: Identity,
    /// Who is signed in. Components read it to show the sign-in form.
    pub session: Signal<Option<Session>>,
    /// Kept out of `session` so refreshing it does not rerender anything.
    id_token: Rc<RefCell<Option<IdToken>>>,
}

impl PartialEq for Api {
    fn eq(&self, other: &Self) -> bool {
        Rc::ptr_eq(&self.id_token, &other.id_token)
    }
}

impl Api {
    pub fn new(
        http: reqwest::Client,
        origin: Url,
        identity: Identity,
        session: Signal<Option<Session>>,
    ) -> Self {
        Self {
            http,
            origin,
            identity,
            session,
            id_token: Rc::default(),
        }
    }

    pub async fn sign_in(&self, email: &str, password: &str) -> Result<()> {
        let (session, token) = self.identity.sign_in(&self.http, email, password).await?;
        session.save();
        *self.id_token.borrow_mut() = Some(token);
        let mut signal = self.session;
        signal.set(Some(session));
        Ok(())
    }

    pub fn sign_out(&self) {
        Session::forget();
        self.id_token.borrow_mut().take();
        let mut signal = self.session;
        signal.set(None);
    }

    /// A valid ID token, refreshed when the cached one is about to expire.
    /// Signs out if the session has been revoked.
    async fn id_token(&self) -> Result<String> {
        if let Some(token) = self.id_token.borrow().as_ref().filter(|t| t.is_fresh()) {
            return Ok(token.token.clone());
        }
        let session = self.session.peek().clone().ok_or(Error::SignedOut)?;
        match self.identity.refresh(&self.http, &session).await {
            Ok(token) => {
                let value = token.token.clone();
                *self.id_token.borrow_mut() = Some(token);
                Ok(value)
            }
            Err(e @ Error::SessionExpired(_)) => {
                self.sign_out();
                Err(e)
            }
            Err(e) => Err(e),
        }
    }

    /// Call `/api/<segments...>`. Each segment is percent-encoded, so ids
    /// and label names can hold any character.
    async fn send(
        &self,
        method: Method,
        segments: &[&str],
        query: &[(&str, &str)],
        body: Option<&(impl Serialize + ?Sized)>,
    ) -> Result<reqwest::Response> {
        let mut url = self.origin.clone();
        url.path_segments_mut()
            .expect("the origin is an http URL")
            .clear()
            .push("api")
            .extend(segments);

        let mut request = self
            .http
            .request(method, url)
            .bearer_auth(self.id_token().await?)
            .query(query);
        if let Some(body) = body {
            request = request.json(body);
        }

        let response = request.send().await?;
        let status = response.status();
        if status.is_success() {
            return Ok(response);
        }

        // Errors are RFC 9457 problem bodies; fall back to the raw text.
        let text = response.text().await?;
        let problem: Value = serde_json::from_str(&text).unwrap_or(Value::Null);
        Err(Error::Api {
            status: status.as_u16(),
            detail: problem["detail"].as_str().map_or(text, String::from),
            existing: problem.get("existing").cloned(),
        })
    }

    async fn get<T: DeserializeOwned>(
        &self,
        segments: &[&str],
        query: &[(&str, &str)],
    ) -> Result<T> {
        decode(self.send(Method::GET, segments, query, None::<&()>).await?).await
    }

    async fn write<T: DeserializeOwned>(
        &self,
        method: Method,
        segments: &[&str],
        body: &(impl Serialize + ?Sized),
    ) -> Result<T> {
        decode(self.send(method, segments, &[], Some(body)).await?).await
    }

    /// A call answered with 204 No Content, or a recipe for `PUT` and
    /// `DELETE` on its parts.
    async fn delete<T: DeserializeOwned>(&self, segments: &[&str]) -> Result<T> {
        let response = self
            .send(Method::DELETE, segments, &[], None::<&()>)
            .await?;
        let text = response.text().await?;
        let text = if text.is_empty() { "null" } else { &text };
        Ok(serde_json::from_str(text)?)
    }

    pub async fn me(&self) -> Result<Me> {
        self.get(&["me"], &[]).await
    }

    // --- Recipes -----------------------------------------------------------

    pub async fn recipes(&self, prefix: &str) -> Result<Vec<RecipeListing>> {
        self.get(&["recipes"], &[("prefix", prefix)]).await
    }

    pub async fn recipe(&self, id: &RecipeId) -> Result<Recipe> {
        self.get(&["recipes", &id.0], &[]).await
    }

    pub async fn create_recipe(&self, input: &NewRecipe) -> Result<Recipe> {
        input.validate()?;
        self.write(Method::POST, &["recipes"], input).await
    }

    pub async fn update_recipe(&self, id: &RecipeId, patch: &RecipePatch) -> Result<Recipe> {
        patch.validate()?;
        self.write(Method::PATCH, &["recipes", &id.0], patch).await
    }

    pub async fn delete_recipe(&self, id: &RecipeId) -> Result<()> {
        self.delete(&["recipes", &id.0]).await
    }

    pub async fn put_requirement(
        &self,
        id: &RecipeId,
        ingredient: &IngredientId,
        input: &RequirementInput,
    ) -> Result<Recipe> {
        input.validate()?;
        let segments = ["recipes", &id.0, "requirements", &ingredient.0];
        self.write(Method::PUT, &segments, input).await
    }

    pub async fn delete_requirement(
        &self,
        id: &RecipeId,
        ingredient: &IngredientId,
    ) -> Result<Recipe> {
        self.delete(&["recipes", &id.0, "requirements", &ingredient.0])
            .await
    }

    pub async fn put_dependency(
        &self,
        id: &RecipeId,
        requisite: &RecipeId,
        input: &DependencyInput,
    ) -> Result<Recipe> {
        if id == requisite {
            return Err(knife_core::Error::SelfDependency.into());
        }
        let segments = ["recipes", &id.0, "dependencies", &requisite.0];
        self.write(Method::PUT, &segments, input).await
    }

    pub async fn delete_dependency(&self, id: &RecipeId, requisite: &RecipeId) -> Result<Recipe> {
        self.delete(&["recipes", &id.0, "dependencies", &requisite.0])
            .await
    }

    /// Tag a recipe, creating the label if it is new.
    pub async fn put_tag(&self, id: &RecipeId, label: &str) -> Result<Recipe> {
        let label = knife_core::ValidName::label(label)?;
        let segments = ["recipes", &id.0, "tags", &label.name];
        decode(self.send(Method::PUT, &segments, &[], None::<&()>).await?).await
    }

    pub async fn delete_tag(&self, id: &RecipeId, label: &str) -> Result<Recipe> {
        self.delete(&["recipes", &id.0, "tags", label]).await
    }

    // --- Ingredients -------------------------------------------------------

    pub async fn ingredients(&self, prefix: &str) -> Result<Vec<Summary<IngredientId>>> {
        self.get(&["ingredients"], &[("prefix", prefix)]).await
    }

    pub async fn ingredient(&self, id: &IngredientId) -> Result<IngredientDetails> {
        self.get(&["ingredients", &id.0], &[]).await
    }

    pub async fn create_ingredient(&self, input: &NewIngredient) -> Result<Ingredient> {
        input.validate()?;
        self.write(Method::POST, &["ingredients"], input).await
    }

    pub async fn update_ingredient(
        &self,
        id: &IngredientId,
        patch: &IngredientPatch,
    ) -> Result<Ingredient> {
        patch.validate()?;
        self.write(Method::PATCH, &["ingredients", &id.0], patch)
            .await
    }

    pub async fn delete_ingredient(&self, id: &IngredientId) -> Result<()> {
        self.delete(&["ingredients", &id.0]).await
    }

    /// Merge `from` into `into`: every recipe using `from` uses `into`
    /// instead, `from` is deleted, and `into` takes `name` if given. `into`
    /// also takes `from`'s flags, so no recipe loses one.
    ///
    /// The API has no transaction across these calls. If one fails, rerun
    /// the merge: recipes already moved no longer use `from`.
    pub async fn merge_ingredient(
        &self,
        from: &IngredientId,
        into: &IngredientId,
        name: Option<String>,
    ) -> Result<Ingredient> {
        if from == into {
            return Err(Error::SelfMerge);
        }
        let source = self.ingredient(from).await?;
        let target = self.ingredient(into).await?.ingredient;

        let flags = target.classification | source.ingredient.classification;
        if flags != target.classification {
            let patch = IngredientPatch {
                dairy: Some(flags.dairy),
                meat: Some(flags.meat),
                gluten: Some(flags.gluten),
                animal_product: Some(flags.animal_product),
                ..Default::default()
            };
            self.update_ingredient(into, &patch).await?;
        }

        for summary in &source.used_in {
            let recipe = self.recipe(&summary.id).await?;
            let Some(moved) = recipe.requirements.get(from) else {
                continue;
            };
            let input = match recipe.requirements.get(into) {
                Some(kept) => RequirementInput::merged(kept, moved),
                None => moved.into(),
            };
            self.put_requirement(&recipe.id, into, &input).await?;
            self.delete_requirement(&recipe.id, from).await?;
        }
        self.delete_ingredient(from).await?;

        // Renamed last, as the new name may be the one `from` held.
        match name.filter(|n| n.trim() != target.name) {
            Some(name) => {
                let patch = IngredientPatch {
                    name: Some(name),
                    ..Default::default()
                };
                self.update_ingredient(into, &patch).await
            }
            None => Ok(self.ingredient(into).await?.ingredient),
        }
    }

    // --- Labels ------------------------------------------------------------

    pub async fn labels(&self, prefix: &str) -> Result<Vec<Label>> {
        self.get(&["labels"], &[("prefix", prefix)]).await
    }

    pub async fn update_label(&self, simple_name: &str, patch: &LabelPatch) -> Result<Label> {
        patch.validate()?;
        self.write(Method::PATCH, &["labels", simple_name], patch)
            .await
    }

    pub async fn delete_label(&self, simple_name: &str) -> Result<()> {
        self.delete(&["labels", simple_name]).await
    }

    /// Merge `from` into `into`: every recipe tagged `from` is tagged `into`
    /// instead, `from` is deleted, and `into` takes `name` if given.
    ///
    /// As for ingredients, rerun the merge if a call fails part way.
    pub async fn merge_label(
        &self,
        from: &Label,
        into: &Label,
        name: Option<String>,
    ) -> Result<Label> {
        if from.simple_name == into.simple_name {
            return Err(Error::SelfMerge);
        }
        let tagged = self.recipes("").await?;
        for recipe in tagged.iter().filter(|r| r.tags.contains(&from.simple_name)) {
            if !recipe.tags.contains(&into.simple_name) {
                self.put_tag(&recipe.id, &into.name).await?;
            }
            self.delete_tag(&recipe.id, &from.simple_name).await?;
        }
        // The server may already have removed the label with its last tag.
        match self.delete_label(&from.simple_name).await {
            Err(e) if e.status() != Some(404) => return Err(e),
            _ => {}
        }

        // Renamed last, as the new name may be the one `from` held.
        let into = match name.filter(|n| n.trim() != into.name) {
            Some(name) => {
                self.update_label(&into.simple_name, &LabelPatch { name })
                    .await?
            }
            None => into.clone(),
        };
        Ok(into)
    }
}

/// Read a JSON body. A body that does not match `T`, as from a server older
/// than this app, is an [`Error::Response`] naming the mismatch rather than
/// a network error.
async fn decode<T: DeserializeOwned>(response: reqwest::Response) -> Result<T> {
    let text = response.text().await?;
    Ok(serde_json::from_str(&text)?)
}

/// The [`Api`] provided by the app root.
pub fn use_api() -> Api {
    use_context()
}
