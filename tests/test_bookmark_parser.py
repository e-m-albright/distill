"""Tests for bookmark parser."""

from app.services.bookmark_parser import parse_chrome_json, parse_netscape_html


def test_parse_netscape_html() -> None:
    """Parse Netscape bookmark HTML."""
    html = """
    <!DOCTYPE NETSCAPE-Bookmark-file-1>
    <META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
    <DL>
    <DT><H3>Folder</H3>
    <DL><p>
    <DT><A HREF="https://example.com" ADD_DATE="1234567890">Example</A>
    <DT><A HREF="https://other.com">Other</A>
    </DL><p>
    </DL>
    """
    entries = list(parse_netscape_html(html))
    assert len(entries) == 2
    assert entries[0].url == "https://example.com"
    assert entries[0].title == "Example"
    assert entries[0].folder == "Folder"
    assert entries[1].url == "https://other.com"
    assert entries[1].title == "Other"


def test_parse_chrome_json() -> None:
    """Parse Chrome bookmarks JSON."""
    data = """
    {
        "roots": {
            "bookmark_bar": {
                "children": [
                    {
                        "type": "url",
                        "name": "Example",
                        "url": "https://example.com"
                    }
                ]
            }
        }
    }
    """
    entries = list(parse_chrome_json(data))
    assert len(entries) == 1
    assert entries[0].url == "https://example.com"
    assert entries[0].title == "Example"
