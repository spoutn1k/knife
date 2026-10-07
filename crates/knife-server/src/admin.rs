//! Member management, for admins. Adding a member can create their Firebase
//! account, and removing one deletes it.

use crate::Auth;
use crate::auth::CurrentUser;
use crate::error::ApiError;
use crate::members::Member;
use crate::routes::{Body, Path};
use axum::extract::State;
use axum::http::StatusCode;
use axum::routing::{get, patch, post};
use axum::{Extension, Json, Router};
use knife_core::input::{MemberPatch, NewMember};
use knife_core::{MemberListing, UserId, simplify};
use std::collections::HashMap;
use std::sync::Arc;

type Result<T> = std::result::Result<T, ApiError>;
type Admin = State<Arc<Auth>>;

pub fn router(auth: Arc<Auth>) -> Router {
    Router::new()
        .route("/members", get(list_members).post(add_member))
        .route("/members/{uid}", patch(update_member).delete(remove_member))
        .route("/members/{uid}/password-reset", post(send_password_reset))
        .with_state(auth)
}

fn listing(uid: UserId, email: Option<String>, member: Member) -> MemberListing {
    MemberListing {
        uid,
        email,
        display_name: member.display_name,
        editor: member.editor,
        admin: member.admin,
    }
}

async fn email_of(auth: &Auth, uid: &UserId) -> Result<Option<String>> {
    let found = auth.accounts.by_uids(std::slice::from_ref(uid)).await?;
    Ok(found.into_iter().next().and_then(|a| a.email))
}

async fn existing(auth: &Auth, uid: &UserId) -> Result<Member> {
    auth.members
        .get(uid)
        .await
        .map_err(ApiError::internal)?
        .ok_or_else(|| ApiError::new(StatusCode::NOT_FOUND, format!("no member {uid}")))
}

async fn list_members(State(auth): Admin) -> Result<Json<Vec<MemberListing>>> {
    let members = auth.members.list().await.map_err(ApiError::internal)?;
    let uids: Vec<UserId> = members.iter().map(|(uid, _)| uid.clone()).collect();
    let mut emails: HashMap<UserId, Option<String>> = auth
        .accounts
        .by_uids(&uids)
        .await?
        .into_iter()
        .map(|a| (a.uid, a.email))
        .collect();

    let mut listed: Vec<MemberListing> = members
        .into_iter()
        .map(|(uid, member)| {
            let email = emails.remove(&uid).flatten();
            listing(uid, email, member)
        })
        .collect();
    listed.sort_by_cached_key(|m| simplify(&m.display_name));
    Ok(Json(listed))
}

/// Makes an account a member, creating it when a password is given.
async fn add_member(
    State(auth): Admin,
    Body(input): Body<NewMember>,
) -> Result<(StatusCode, Json<MemberListing>)> {
    let name = input.validate()?;
    let email = input.email.trim();

    let account = auth.accounts.by_email(email).await?;
    let uid = match (account, &input.password) {
        (Some(account), None) => account.uid,
        (None, Some(password)) => auth.accounts.create(email, password, &name.name).await?,
        (Some(_), Some(_)) => {
            return Err(ApiError::new(
                StatusCode::CONFLICT,
                format!("{email} already has an account: leave the password empty to add it"),
            ));
        }
        (None, None) => {
            return Err(ApiError::new(
                StatusCode::BAD_REQUEST,
                format!("{email} has no account: give a password to create one"),
            ));
        }
    };

    if auth
        .members
        .get(&uid)
        .await
        .map_err(ApiError::internal)?
        .is_some()
    {
        return Err(ApiError::new(
            StatusCode::CONFLICT,
            format!("{email} is already a member"),
        ));
    }
    let member = Member {
        display_name: name.name,
        editor: input.editor,
        admin: input.admin,
    };
    auth.members
        .set(&uid, &member)
        .await
        .map_err(ApiError::internal)?;

    Ok((
        StatusCode::CREATED,
        Json(listing(uid, Some(email.to_owned()), member)),
    ))
}

async fn update_member(
    State(auth): Admin,
    Extension(user): Extension<CurrentUser>,
    Path(uid): Path<UserId>,
    Body(patch): Body<MemberPatch>,
) -> Result<Json<MemberListing>> {
    let name = patch.validate()?;
    // There would be no admin left to undo it.
    if uid == user.uid && patch.admin == Some(false) {
        return Err(ApiError::new(
            StatusCode::BAD_REQUEST,
            "you cannot remove your own admin rights",
        ));
    }

    let mut member = existing(&auth, &uid).await?;
    if let Some(name) = name {
        member.display_name = name.name;
    }
    if let Some(editor) = patch.editor {
        member.editor = editor;
    }
    if let Some(admin) = patch.admin {
        member.admin = admin;
    }

    if let Some(password) = &patch.password {
        auth.accounts.set_password(&uid, password).await?;
    }
    auth.members
        .set(&uid, &member)
        .await
        .map_err(ApiError::internal)?;

    let email = email_of(&auth, &uid).await?;
    Ok(Json(listing(uid, email, member)))
}

/// Emails the member a link to choose a new password.
async fn send_password_reset(State(auth): Admin, Path(uid): Path<UserId>) -> Result<StatusCode> {
    existing(&auth, &uid).await?;
    let email = email_of(&auth, &uid).await?.ok_or_else(|| {
        ApiError::new(
            StatusCode::BAD_REQUEST,
            "this member has no account with an email",
        )
    })?;
    auth.accounts.send_password_reset(&email).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// Removes a member and deletes their account.
async fn remove_member(
    State(auth): Admin,
    Extension(user): Extension<CurrentUser>,
    Path(uid): Path<UserId>,
) -> Result<StatusCode> {
    if uid == user.uid {
        return Err(ApiError::new(
            StatusCode::BAD_REQUEST,
            "you cannot remove yourself",
        ));
    }
    existing(&auth, &uid).await?;

    // Membership first: without it, a leftover account cannot get in.
    auth.members
        .remove(&uid)
        .await
        .map_err(ApiError::internal)?;
    auth.accounts.delete(&uid).await?;
    Ok(StatusCode::NO_CONTENT)
}
