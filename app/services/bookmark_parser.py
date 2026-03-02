"""Parse bookmark exports (Netscape HTML and Chrome JSON)."""

import json
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Generator


class BookmarkEntry(BaseModel):
    """A single bookmark entry."""

    url: str
    title: str
    folder: str = ""
    added: str | None = None


def parse_netscape_html(html: str) -> "Generator[BookmarkEntry, None, None]":
    """Parse Netscape-style bookmark HTML (Chrome, Firefox export)."""
    parser = _NetscapeHTMLParser()
    parser.feed(html)
    yield from parser.bookmarks


def parse_chrome_json(data: str) -> "Generator[BookmarkEntry, None, None]":
    """Parse Chrome bookmarks.json format."""
    obj = json.loads(data)
    roots = obj.get("roots", {})
    for key in ("bookmark_bar", "other", "synced"):
        if key in roots and isinstance(roots[key], dict):
            folder_name = {"bookmark_bar": "Bookmarks Bar", "other": "Other", "synced": "Synced"}.get(key, key)
            yield from _extract_chrome_bookmarks(roots[key], folder_name)


def _extract_chrome_bookmarks(
    node: dict[str, Any],
    folder_path: str,
) -> "Generator[BookmarkEntry, None, None]":
    """Recursively extract bookmarks from Chrome node (folder or url)."""
    for child in node.get("children", []):
        if not isinstance(child, dict):
            continue
        child_dict = cast(dict[str, Any], child)
        if child_dict.get("type") == "url":
            child_url: str = child_dict.get("url") or ""
            if child_url:
                child_title: str = str(child_dict.get("name") or child_dict.get("title") or "")
                date_added: Any = child_dict.get("date_added") or child_dict.get("dateAdded")
                yield BookmarkEntry(
                    url=child_url,
                    title=child_title,
                    folder=folder_path,
                    added=str(date_added) if date_added else None,
                )
        elif child_dict.get("type") == "folder":
            folder_name: str = str(child_dict.get("name") or child_dict.get("title") or "")
            new_path = f"{folder_path}/{folder_name}" if folder_path else folder_name
            yield from _extract_chrome_bookmarks(child_dict, new_path)


class _NetscapeHTMLParser(HTMLParser):
    """Parse Netscape bookmark HTML format."""

    # <DT><A HREF="url" ADD_DATE="..." PRIVATE="0">title</A>
    # Folders: <DT><H3>Folder Name</H3><DL><p>...</DL>

    def __init__(self) -> None:
        super().__init__()
        self.bookmarks: list[BookmarkEntry] = []
        self._folder_stack: list[str] = []
        self._in_anchor = False
        self._in_h3 = False
        self._current_url = ""
        self._current_title = ""
        self._current_add_date: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "h3":
            self._in_h3 = True
        elif tag == "a":
            self._in_anchor = True
            self._current_url = attrs_dict.get("href", "")
            self._current_add_date = attrs_dict.get("add_date")
        elif tag == "dl" and self._folder_stack:
            pass  # Nested folder
        elif tag == "dl":
            pass

    def handle_endtag(self, tag: str) -> None:
        if tag == "h3":
            self._in_h3 = False
        elif tag == "a":
            if self._in_anchor and self._current_url and self._current_url.startswith("http"):
                folder = "/".join(self._folder_stack)
                self.bookmarks.append(
                    BookmarkEntry(
                        url=self._current_url,
                        title=self._current_title.strip() or self._current_url,
                        folder=folder,
                        added=self._current_add_date,
                    ),
                )
            self._in_anchor = False
            self._current_url = ""
            self._current_title = ""
            self._current_add_date = None
        elif tag == "dl" and self._folder_stack:
            self._folder_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._in_h3:
            self._folder_stack.append(data.strip())
        elif self._in_anchor:
            self._current_title += data
