//! Recipe text, written in markdown, as HTML.

use pulldown_cmark::{CowStr, Event, Options, Parser, Tag};

/// Render `text` to HTML that is safe to insert in the page: raw HTML is
/// shown as text, and links may only point to web and mail addresses.
///
/// Single line breaks are kept, as recipes were written as plain text
/// before markdown, one step per line.
pub fn to_html(text: &str) -> String {
    let options = Options::ENABLE_STRIKETHROUGH | Options::ENABLE_TABLES;
    let events = Parser::new_ext(text, options).map(|event| match event {
        Event::Html(html) | Event::InlineHtml(html) => Event::Text(html),
        Event::SoftBreak => Event::HardBreak,
        Event::Start(Tag::Link {
            link_type,
            dest_url,
            title,
            id,
        }) => Event::Start(Tag::Link {
            link_type,
            dest_url: safe_url(dest_url),
            title,
            id,
        }),
        Event::Start(Tag::Image {
            link_type,
            dest_url,
            title,
            id,
        }) => Event::Start(Tag::Image {
            link_type,
            dest_url: safe_url(dest_url),
            title,
            id,
        }),
        event => event,
    });

    let mut html = String::new();
    pulldown_cmark::html::push_html(&mut html, events);
    html
}

/// `url` if it is a web or mail address, or relative; otherwise nothing, so
/// `javascript:` and `data:` links do not run.
fn safe_url(url: CowStr<'_>) -> CowStr<'_> {
    let scheme = url
        .split_once(':')
        .map(|(scheme, _)| scheme.to_ascii_lowercase())
        .filter(|scheme| !scheme.contains(['/', '?', '#']));
    match scheme.as_deref() {
        None | Some("http" | "https" | "mailto") => url,
        Some(_) => CowStr::Borrowed(""),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renders_markdown() {
        let html = to_html("Some **bold** step.\n\n- one\n- two");
        assert!(html.contains("<strong>bold</strong>"));
        assert!(html.contains("<li>one</li>"));
    }

    #[test]
    fn keeps_line_breaks() {
        assert_eq!(to_html("Mix.\nBake."), "<p>Mix.<br />\nBake.</p>\n");
    }

    #[test]
    fn escapes_raw_html() {
        let html = to_html("<script>alert(1)</script> and <b onclick=x>b</b>");
        assert!(!html.contains("<script>"));
        assert!(!html.contains("<b "));
        assert!(html.contains("&lt;script&gt;"));
    }

    #[test]
    fn drops_script_links() {
        assert!(!to_html("[x](javascript:alert(1))").contains("javascript"));
        assert!(!to_html("[x](JavaScript:alert(1))").contains("JavaScript"));
        assert!(!to_html("![x](data:image/png;base64,AA)").contains("data:"));
    }

    #[test]
    fn keeps_web_links() {
        assert!(to_html("[x](https://example.com)").contains("href=\"https://example.com\""));
        assert!(to_html("[x](/recipes/1)").contains("href=\"/recipes/1\""));
    }
}
