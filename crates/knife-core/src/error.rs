use crate::RecipeId;

/// Rule violations detected by this crate. Lookups and conflicts against
/// stored data (not found, name taken) belong to the server.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum Error {
    #[error("name is empty")]
    EmptyName,

    #[error("names are limited to {0} characters")]
    NameTooLong(usize),

    #[error("label names cannot contain whitespace: {0:?}")]
    LabelWhitespace(String),

    #[error("quantity is empty")]
    EmptyQuantity,

    #[error("nothing to update")]
    EmptyPatch,

    #[error("a recipe cannot depend on itself")]
    SelfDependency,

    #[error("adding this dependency would create a cycle")]
    DependencyCycle,

    /// The caller did not load a recipe the computation needed. This is a
    /// bug in the caller, not bad user input.
    #[error("recipe {0} is missing from the loaded graph")]
    MissingRecipe(RecipeId),
}
