"""API integration tests for bookmark endpoints."""

import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ingest_html(client: AsyncClient) -> None:
    """Ingest HTML bookmark file via API."""
    html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
    <DL><DT><A HREF="https://example.com">Example</A></DL>"""
    files = {"file": ("bookmarks.html", io.BytesIO(html.encode()), "text/html")}
    r = await client.post("/ingest/bookmarks", files=files, data={"format": "html"})
    assert r.status_code == 200
    data = r.json()
    assert data["ingested"] == 1
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_bookmarks(client: AsyncClient) -> None:
    """List bookmarks after ingest."""
    html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
    <DL><DT><A HREF="https://a.com">A</A><DT><A HREF="https://b.com">B</A></DL>"""
    files = {"file": ("bookmarks.html", io.BytesIO(html.encode()), "text/html")}
    await client.post("/ingest/bookmarks", files=files, data={"format": "html"})

    r = await client.get("/bookmarks", params={"status": "active"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_discard_and_restore_bulk(client: AsyncClient) -> None:
    """Discard and restore bookmarks via bulk endpoints."""
    html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
    <DL><DT><A HREF="https://c.com">C</A><DT><A HREF="https://d.com">D</A></DL>"""
    files = {"file": ("bookmarks.html", io.BytesIO(html.encode()), "text/html")}
    await client.post("/ingest/bookmarks", files=files, data={"format": "html"})

    r = await client.get("/bookmarks", params={"status": "active"})
    ids = [item["id"] for item in r.json()["items"]]

    r = await client.post("/bookmarks/discard-bulk", json={"ids": ids})
    assert r.status_code == 200
    assert r.json()["discarded"] == 2

    r = await client.get("/bookmarks", params={"status": "active"})
    assert r.json()["total"] == 0

    r = await client.post("/bookmarks/restore-bulk", json={"ids": ids})
    assert r.status_code == 200
    assert r.json()["restored"] == 2

    r = await client.get("/bookmarks", params={"status": "active"})
    assert r.json()["total"] == 2


@pytest.mark.asyncio
async def test_move_bulk(client: AsyncClient) -> None:
    """Move bookmarks to view status."""
    html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
    <DL><DT><A HREF="https://e.com">E</A></DL>"""
    files = {"file": ("bookmarks.html", io.BytesIO(html.encode()), "text/html")}
    await client.post("/ingest/bookmarks", files=files, data={"format": "html"})

    r = await client.get("/bookmarks", params={"status": "active"})
    ids = [item["id"] for item in r.json()["items"]]

    r = await client.post("/bookmarks/move-bulk", json={"ids": ids, "status": "view"})
    assert r.status_code == 200
    assert r.json()["moved"] == 1

    r = await client.get("/bookmarks", params={"status": "view"})
    assert r.json()["total"] == 1
