//! HTTP handlers. They parse requests and call [`Store`]; the rules live in
//! the store and in `knife-core`.

use crate::auth::CurrentUser;
use crate::error::ApiError;
use crate::store::Store;
use axum::extract::{FromRequest, FromRequestParts, State};
use axum::http::StatusCode;
use axum::routing::{get, put};
use axum::{Extension, Json, Router};
use knife_core::input::{
    DependencyInput, IngredientPatch, LabelPatch, NewIngredient, NewRecipe, RecipePatch,
    RequirementInput,
};
use knife_core::{
    Ingredient, IngredientDetails, IngredientId, Label, LabelDetails, Recipe, RecipeDetails,
    RecipeId, RecipeListing, Summary,
};
use serde::Deserialize;
use std::sync::Arc;

type Result<T> = std::result::Result<T, ApiError>;
type Db = State<Arc<Store>>;

/// A JSON body; malformed or unknown fields give a problem response.
#[derive(FromRequest)]
#[from_request(via(axum::Json), rejection(ApiError))]
pub struct Body<T>(pub T);

#[derive(FromRequestParts)]
#[from_request(via(axum::extract::Path), rejection(ApiError))]
pub struct Path<T>(pub T);

#[derive(FromRequestParts)]
#[from_request(via(axum::extract::Query), rejection(ApiError))]
pub struct Query<T>(T);

/// `?prefix=` on list endpoints: matches the start of the simplified name.
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Search {
    #[serde(default)]
    prefix: String,
}

pub fn router(store: Arc<Store>) -> Router {
    Router::new()
        .route(
            "/ingredients",
            get(list_ingredients).post(create_ingredient),
        )
        .route(
            "/ingredients/{id}",
            get(get_ingredient)
                .patch(update_ingredient)
                .delete(delete_ingredient),
        )
        .route("/recipes", get(list_recipes).post(create_recipe))
        .route(
            "/recipes/{id}",
            get(get_recipe).patch(update_recipe).delete(delete_recipe),
        )
        .route(
            "/recipes/{id}/requirements/{ingredient}",
            put(put_requirement).delete(delete_requirement),
        )
        .route(
            "/recipes/{id}/dependencies/{requisite}",
            put(put_dependency).delete(delete_dependency),
        )
        .route(
            "/recipes/{id}/tags/{label}",
            put(put_tag).delete(delete_tag),
        )
        .route("/labels", get(list_labels))
        .route(
            "/labels/{label}",
            get(get_label).patch(update_label).delete(delete_label),
        )
        .with_state(store)
}

async fn list_ingredients(
    State(store): Db,
    Query(search): Query<Search>,
) -> Result<Json<Vec<Summary<IngredientId>>>> {
    Ok(Json(store.list_ingredients(&search.prefix).await?))
}

async fn create_ingredient(
    State(store): Db,
    Body(input): Body<NewIngredient>,
) -> Result<(StatusCode, Json<Ingredient>)> {
    Ok((
        StatusCode::CREATED,
        Json(store.create_ingredient(&input).await?),
    ))
}

async fn get_ingredient(
    State(store): Db,
    Path(id): Path<IngredientId>,
) -> Result<Json<IngredientDetails>> {
    Ok(Json(store.get_ingredient(&id).await?))
}

async fn update_ingredient(
    State(store): Db,
    Path(id): Path<IngredientId>,
    Body(patch): Body<IngredientPatch>,
) -> Result<Json<Ingredient>> {
    Ok(Json(store.update_ingredient(&id, &patch).await?))
}

async fn delete_ingredient(State(store): Db, Path(id): Path<IngredientId>) -> Result<StatusCode> {
    store.delete_ingredient(&id).await?;
    Ok(StatusCode::NO_CONTENT)
}

async fn list_recipes(
    State(store): Db,
    Query(search): Query<Search>,
) -> Result<Json<Vec<RecipeListing>>> {
    Ok(Json(store.list_recipes(&search.prefix).await?))
}

async fn create_recipe(
    State(store): Db,
    Extension(user): Extension<CurrentUser>,
    Body(input): Body<NewRecipe>,
) -> Result<(StatusCode, Json<Recipe>)> {
    Ok((
        StatusCode::CREATED,
        Json(store.create_recipe(&input, &user.uid).await?),
    ))
}

async fn get_recipe(State(store): Db, Path(id): Path<RecipeId>) -> Result<Json<RecipeDetails>> {
    Ok(Json(store.get_recipe(&id).await?))
}

async fn update_recipe(
    State(store): Db,
    Extension(user): Extension<CurrentUser>,
    Path(id): Path<RecipeId>,
    Body(patch): Body<RecipePatch>,
) -> Result<Json<Recipe>> {
    Ok(Json(store.update_recipe(&id, &patch, &user.uid).await?))
}

async fn delete_recipe(State(store): Db, Path(id): Path<RecipeId>) -> Result<StatusCode> {
    store.delete_recipe(&id).await?;
    Ok(StatusCode::NO_CONTENT)
}

async fn put_requirement(
    State(store): Db,
    Extension(user): Extension<CurrentUser>,
    Path((id, ingredient)): Path<(RecipeId, IngredientId)>,
    Body(input): Body<RequirementInput>,
) -> Result<Json<Recipe>> {
    Ok(Json(
        store
            .put_requirement(&id, &ingredient, &input, &user.uid)
            .await?,
    ))
}

async fn delete_requirement(
    State(store): Db,
    Extension(user): Extension<CurrentUser>,
    Path((id, ingredient)): Path<(RecipeId, IngredientId)>,
) -> Result<Json<Recipe>> {
    Ok(Json(
        store
            .delete_requirement(&id, &ingredient, &user.uid)
            .await?,
    ))
}

async fn put_dependency(
    State(store): Db,
    Extension(user): Extension<CurrentUser>,
    Path((id, requisite)): Path<(RecipeId, RecipeId)>,
    Body(input): Body<DependencyInput>,
) -> Result<Json<Recipe>> {
    Ok(Json(
        store
            .put_dependency(&id, &requisite, &input, &user.uid)
            .await?,
    ))
}

async fn delete_dependency(
    State(store): Db,
    Extension(user): Extension<CurrentUser>,
    Path((id, requisite)): Path<(RecipeId, RecipeId)>,
) -> Result<Json<Recipe>> {
    Ok(Json(
        store.delete_dependency(&id, &requisite, &user.uid).await?,
    ))
}

async fn put_tag(
    State(store): Db,
    Extension(user): Extension<CurrentUser>,
    Path((id, label)): Path<(RecipeId, String)>,
) -> Result<Json<Recipe>> {
    Ok(Json(store.put_tag(&id, &label, &user.uid).await?))
}

async fn delete_tag(
    State(store): Db,
    Extension(user): Extension<CurrentUser>,
    Path((id, label)): Path<(RecipeId, String)>,
) -> Result<Json<Recipe>> {
    Ok(Json(store.delete_tag(&id, &label, &user.uid).await?))
}

async fn list_labels(State(store): Db, Query(search): Query<Search>) -> Result<Json<Vec<Label>>> {
    Ok(Json(store.list_labels(&search.prefix).await?))
}

async fn get_label(State(store): Db, Path(label): Path<String>) -> Result<Json<LabelDetails>> {
    Ok(Json(store.get_label(&label).await?))
}

async fn update_label(
    State(store): Db,
    Path(label): Path<String>,
    Body(patch): Body<LabelPatch>,
) -> Result<Json<Label>> {
    Ok(Json(store.update_label(&label, &patch).await?))
}

async fn delete_label(State(store): Db, Path(label): Path<String>) -> Result<StatusCode> {
    store.delete_label(&label).await?;
    Ok(StatusCode::NO_CONTENT)
}
