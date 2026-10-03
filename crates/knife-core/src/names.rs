use crate::Error;

/// Canonical form of a name, used for uniqueness and prefix search.
///
/// Lowercase, transliterated to ASCII, spaces, apostrophes and slashes
/// replaced by `_`: "Crème Brûlée" and "creme brulee" both become
/// `creme_brulee`. The result is safe in a Firestore document id.
pub fn simplify(name: &str) -> String {
    deunicode::deunicode(&name.trim().to_lowercase())
        .to_lowercase()
        .replace([' ', '\'', '/'], "_")
}

/// Longest accepted name, in characters.
pub const MAX_NAME_LEN: usize = 200;

/// Bounds for a Firestore prefix query on a `simple_name` field:
/// `field >= start && field < end`.
pub fn prefix_bounds(prefix: &str) -> (String, String) {
    let start = simplify(prefix);
    let end = format!("{start}\u{f8ff}");
    (start, end)
}

/// A display name with its canonical form.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidName {
    pub name: String,
    pub simple_name: String,
}

impl ValidName {
    /// Validate a recipe or ingredient name.
    pub fn new(raw: &str) -> Result<Self, Error> {
        let name = raw.trim();
        let simple_name = simplify(name);

        if simple_name.is_empty() {
            return Err(Error::EmptyName);
        }
        if name.chars().count() > MAX_NAME_LEN {
            return Err(Error::NameTooLong(MAX_NAME_LEN));
        }

        Ok(Self {
            name: name.to_owned(),
            simple_name,
        })
    }

    /// Validate a label name. Labels are single words.
    pub fn label(raw: &str) -> Result<Self, Error> {
        let valid = Self::new(raw)?;

        if valid.name.contains(char::is_whitespace) {
            return Err(Error::LabelWhitespace(valid.name));
        }

        Ok(valid)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn simplify_folds_case_and_accents() {
        assert_eq!(simplify("Crème Brûlée"), "creme_brulee");
        assert_eq!(simplify("creme brulee"), "creme_brulee");
        assert_eq!(simplify("Œufs"), "oeufs");
    }

    #[test]
    fn simplify_replaces_apostrophes() {
        assert_eq!(simplify("Mom's pie"), "mom_s_pie");
        assert_eq!(simplify("Mom’s pie"), "mom_s_pie");
    }

    #[test]
    fn simplify_replaces_slashes() {
        assert_eq!(simplify("1/2 lemon"), "1_2_lemon");
    }

    #[test]
    fn long_names_are_rejected() {
        let long = "a".repeat(MAX_NAME_LEN + 1);
        assert_eq!(ValidName::new(&long), Err(Error::NameTooLong(MAX_NAME_LEN)));
        assert!(ValidName::new(&long[1..]).is_ok());
    }

    #[test]
    fn names_are_trimmed() {
        let valid = ValidName::new("  Pasta ").unwrap();
        assert_eq!(valid.name, "Pasta");
        assert_eq!(valid.simple_name, "pasta");
    }

    #[test]
    fn empty_names_are_rejected() {
        assert_eq!(ValidName::new(""), Err(Error::EmptyName));
        assert_eq!(ValidName::new("   "), Err(Error::EmptyName));
    }

    #[test]
    fn labels_are_single_words() {
        assert!(ValidName::label("french").is_ok());
        assert_eq!(
            ValidName::label("two words"),
            Err(Error::LabelWhitespace("two words".into()))
        );
    }

    #[test]
    fn prefix_bounds_cover_the_prefix() {
        let (start, end) = prefix_bounds("Pâte");
        assert_eq!(start, "pate");
        assert!("pate_brisee" >= start.as_str() && "pate_brisee" < end.as_str());
        assert!("pasta" < start.as_str());
    }
}
