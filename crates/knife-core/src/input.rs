//! Request bodies. Unknown fields and wrongly typed values are rejected at
//! deserialization, so `{"dairy": "yes"}` never reaches storage.

use crate::{Classification, Error, Requirement, ValidName};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NewRecipe {
    pub name: String,
    #[serde(default)]
    pub author: String,
    #[serde(default)]
    pub directions: String,
    #[serde(default)]
    pub information: String,
}

impl NewRecipe {
    pub fn validate(&self) -> Result<ValidName, Error> {
        ValidName::new(&self.name)
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RecipePatch {
    pub name: Option<String>,
    pub author: Option<String>,
    pub directions: Option<String>,
    pub information: Option<String>,
}

impl RecipePatch {
    /// Returns the validated new name, if the patch renames the recipe.
    pub fn validate(&self) -> Result<Option<ValidName>, Error> {
        if *self == Self::default() {
            return Err(Error::EmptyPatch);
        }
        self.name.as_deref().map(ValidName::new).transpose()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct NewIngredient {
    pub name: String,
    #[serde(default)]
    pub dairy: bool,
    #[serde(default)]
    pub meat: bool,
    #[serde(default)]
    pub gluten: bool,
    #[serde(default)]
    pub animal_product: bool,
}

impl NewIngredient {
    pub fn validate(&self) -> Result<ValidName, Error> {
        ValidName::new(&self.name)
    }

    pub fn classification(&self) -> Classification {
        Classification {
            dairy: self.dairy,
            meat: self.meat,
            gluten: self.gluten,
            animal_product: self.animal_product,
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct IngredientPatch {
    pub name: Option<String>,
    pub dairy: Option<bool>,
    pub meat: Option<bool>,
    pub gluten: Option<bool>,
    pub animal_product: Option<bool>,
}

impl IngredientPatch {
    /// Returns the validated new name, if the patch renames the ingredient.
    pub fn validate(&self) -> Result<Option<ValidName>, Error> {
        if *self == Self::default() {
            return Err(Error::EmptyPatch);
        }
        self.name.as_deref().map(ValidName::new).transpose()
    }

    /// The ingredient's classification after applying this patch.
    pub fn apply(&self, current: Classification) -> Classification {
        Classification {
            dairy: self.dairy.unwrap_or(current.dairy),
            meat: self.meat.unwrap_or(current.meat),
            gluten: self.gluten.unwrap_or(current.gluten),
            animal_product: self.animal_product.unwrap_or(current.animal_product),
        }
    }
}

/// A quantity is free text, but clients may send a plain number (`4`).
fn quantity<'de, D: serde::Deserializer<'de>>(deserializer: D) -> Result<String, D::Error> {
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum Quantity {
        Text(String),
        Integer(i64),
        Decimal(f64),
    }

    Ok(match Quantity::deserialize(deserializer)? {
        Quantity::Text(text) => text.trim().to_owned(),
        Quantity::Integer(n) => n.to_string(),
        Quantity::Decimal(n) => n.to_string(),
    })
}

/// Body of `PUT /recipes/{id}/requirements/{ingredient_id}`. The PUT replaces
/// the whole requirement, so `quantity` is required.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RequirementInput {
    #[serde(deserialize_with = "quantity")]
    pub quantity: String,
    #[serde(default)]
    pub optional: bool,
    #[serde(default)]
    pub group: String,
}

impl From<&Requirement> for RequirementInput {
    fn from(requirement: &Requirement) -> Self {
        Self {
            quantity: requirement.quantity.clone(),
            optional: requirement.optional,
            group: requirement.group.clone(),
        }
    }
}

impl RequirementInput {
    /// One line for a recipe that required both of two merged ingredients:
    /// the quantities are joined ("100g + 50g"), the line is optional only if
    /// both were, and `kept`'s group wins unless it has none.
    pub fn merged(kept: &Requirement, merged: &Requirement) -> Self {
        let quantity = [&kept.quantity, &merged.quantity]
            .into_iter()
            .filter(|q| !q.is_empty())
            .map(String::as_str)
            .collect::<Vec<_>>()
            .join(" + ");
        let group = if kept.group.is_empty() {
            &merged.group
        } else {
            &kept.group
        };
        Self {
            quantity,
            optional: kept.optional && merged.optional,
            group: group.clone(),
        }
    }

    pub fn validate(&self) -> Result<(), Error> {
        if self.quantity.is_empty() {
            return Err(Error::EmptyQuantity);
        }
        Ok(())
    }
}

/// Body of `PUT /recipes/{id}/dependencies/{requisite_id}`. Unlike a
/// requirement, a dependency may leave its quantity empty.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DependencyInput {
    #[serde(default, deserialize_with = "quantity")]
    pub quantity: String,
    #[serde(default)]
    pub optional: bool,
}

/// Body of `PATCH /labels/{simple_name}`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LabelPatch {
    pub name: String,
}

impl LabelPatch {
    pub fn validate(&self) -> Result<ValidName, Error> {
        ValidName::label(&self.name)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{from_value, json};

    #[test]
    fn unknown_fields_are_rejected() {
        assert!(from_value::<NewRecipe>(json!({"name": "Pie", "owner": "me"})).is_err());
        assert!(from_value::<RecipePatch>(json!({"foo": 1})).is_err());
    }

    #[test]
    fn wrong_types_are_rejected() {
        assert!(from_value::<IngredientPatch>(json!({"dairy": "yes"})).is_err());
        assert!(from_value::<NewIngredient>(json!({"name": "Butter", "dairy": 1})).is_err());
    }

    #[test]
    fn defaults_apply() {
        let ingredient: NewIngredient = from_value(json!({"name": "Butter"})).unwrap();
        assert_eq!(ingredient.classification(), Classification::default());

        let dependency: DependencyInput = from_value(json!({})).unwrap();
        assert_eq!(dependency, DependencyInput::default());

        let requirement: RequirementInput = from_value(json!({"quantity": "100g"})).unwrap();
        assert!(!requirement.optional);
        assert_eq!(requirement.group, "");
    }

    #[test]
    fn requirement_needs_quantity() {
        assert!(from_value::<RequirementInput>(json!({"optional": true})).is_err());
        assert!(from_value::<RequirementInput>(json!({"quantity": null})).is_err());

        let blank: RequirementInput = from_value(json!({"quantity": "  "})).unwrap();
        assert_eq!(blank.validate(), Err(Error::EmptyQuantity));
    }

    #[test]
    fn quantities_may_be_numbers() {
        let input: RequirementInput = from_value(json!({"quantity": 4})).unwrap();
        assert_eq!(input.quantity, "4");
        let input: DependencyInput = from_value(json!({"quantity": 0.5})).unwrap();
        assert_eq!(input.quantity, "0.5");
        assert!(from_value::<DependencyInput>(json!({"quantity": true})).is_err());
    }

    #[test]
    fn empty_patches_are_rejected() {
        assert_eq!(RecipePatch::default().validate(), Err(Error::EmptyPatch));
        assert_eq!(
            IngredientPatch::default().validate(),
            Err(Error::EmptyPatch)
        );
    }

    #[test]
    fn patch_names_are_validated() {
        let patch = RecipePatch {
            name: Some("  ".into()),
            ..Default::default()
        };
        assert_eq!(patch.validate(), Err(Error::EmptyName));

        let patch = RecipePatch {
            directions: Some("Bake".into()),
            ..Default::default()
        };
        assert_eq!(patch.validate(), Ok(None));
    }

    #[test]
    fn ingredient_patch_keeps_unset_flags() {
        let current = Classification {
            dairy: true,
            gluten: true,
            ..Default::default()
        };
        let patch = IngredientPatch {
            gluten: Some(false),
            meat: Some(true),
            ..Default::default()
        };

        let next = patch.apply(current);
        assert!(next.dairy && next.meat && !next.gluten && !next.animal_product);
    }

    fn requirement(quantity: &str, optional: bool, group: &str) -> Requirement {
        Requirement {
            name: "Onion".into(),
            classification: Classification::default(),
            quantity: quantity.into(),
            optional,
            group: group.into(),
        }
    }

    #[test]
    fn merged_requirements_join_quantities() {
        let kept = requirement("1", false, "");
        let merged = requirement("2 small", true, "for the sauce");

        let input = RequirementInput::merged(&kept, &merged);
        assert_eq!(input.quantity, "1 + 2 small");
        assert!(!input.optional);
        assert_eq!(input.group, "for the sauce");
        assert_eq!(input.validate(), Ok(()));
    }

    #[test]
    fn merged_requirements_keep_the_kept_group() {
        let kept = requirement("1", true, "garnish");
        let merged = requirement("1", true, "sauce");

        let input = RequirementInput::merged(&kept, &merged);
        assert!(input.optional);
        assert_eq!(input.group, "garnish");
    }

    #[test]
    fn label_patch_rejects_spaces() {
        let patch = LabelPatch {
            name: "two words".into(),
        };
        assert!(patch.validate().is_err());
    }
}
