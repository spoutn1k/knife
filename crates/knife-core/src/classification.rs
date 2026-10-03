use serde::{Deserialize, Serialize};
use std::ops::{BitOr, BitOrAssign};

/// Dietary flags. A recipe's classification is the union of its ingredients'
/// flags and of the recipes it depends on. Optional ingredients count.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default)]
pub struct Classification {
    pub dairy: bool,
    pub meat: bool,
    pub gluten: bool,
    pub animal_product: bool,
}

impl BitOr for Classification {
    type Output = Self;

    fn bitor(self, other: Self) -> Self {
        Self {
            dairy: self.dairy | other.dairy,
            meat: self.meat | other.meat,
            gluten: self.gluten | other.gluten,
            animal_product: self.animal_product | other.animal_product,
        }
    }
}

impl BitOrAssign for Classification {
    fn bitor_assign(&mut self, other: Self) {
        *self = *self | other;
    }
}

impl FromIterator<Classification> for Classification {
    fn from_iter<I: IntoIterator<Item = Classification>>(iter: I) -> Self {
        iter.into_iter().fold(Self::default(), BitOr::bitor)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn union_of_flags() {
        let dairy = Classification {
            dairy: true,
            ..Default::default()
        };
        let meat = Classification {
            meat: true,
            ..Default::default()
        };

        let both: Classification = [dairy, meat].into_iter().collect();
        assert!(both.dairy && both.meat && !both.gluten && !both.animal_product);
    }

    #[test]
    fn empty_union_is_unflagged() {
        let none: Classification = std::iter::empty().collect();
        assert_eq!(none, Classification::default());
    }
}
