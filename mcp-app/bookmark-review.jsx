/**
 * Bookmark Review UI — improved for MCP App integration.
 *
 * Data shape: { overview, items: [{ id, title, url, summary, key_points, keep }] }
 * Matches DistilledBrief + bookmark ids for discard_bookmarks / promote_bookmarks.
 *
 * Improvements over Claude's version:
 * - Summary + key points visible (the whole point of distillation)
 * - AI keep/discard suggestion surfaced
 * - Promote for deeper review (not just discard)
 * - Distinctive design (warm editorial, not generic gray)
 * - callServerTool-ready (pass onDiscard, onPromote when wired to MCP)
 */
import { useState } from "react";

// Sample data matching distill output + ids (for demo; MCP would pass via ontoolresult)
const SAMPLE_BRIEF = {
  overview:
    "Mostly low-value: Google searches, untitled YouTube shorts, checkout pages. A few book/article links worth keeping.",
  items: [
    {
      id: 387,
      title: "plato books",
      url: "https://www.google.com/search?q=plato+books",
      summary: "Bare Google search query. No article content.",
      key_points: [],
      keep: false,
    },
    {
      id: 388,
      title: "voltaire books",
      url: "https://www.google.com/search?q=voltaire+books",
      summary: "Google search. No substantive content.",
      key_points: [],
      keep: false,
    },
    {
      id: 420,
      title: "nyt spiked cider",
      url: "https://www.google.com/search?q=nyt+spiked+cider",
      summary: "Recipe search. Could be useful if you find the actual article.",
      key_points: ["Recipe-related"],
      keep: false,
    },
    {
      id: 562,
      title: "ministry for the future obama",
      url: "https://www.google.com/search?q=the+ministry+for+the+future+obama",
      summary: "Search for Obama's book list mention. Might lead to a good article.",
      key_points: ["Book recommendation context"],
      keep: true,
    },
    {
      id: 684,
      title: "Big Bluff Ranch Checkout",
      url: "https://www.bigbluffranch.com/checkout?cartToken=...",
      summary: "Checkout/cart page. Transactional, no lasting value.",
      key_points: [],
      keep: false,
    },
  ],
  discarded_count: 3,
};

const TYPE_LABELS = {
  all: "All",
  discard: "Suggested discard",
  keep: "Suggested keep",
};

export default function BookmarkReview({ brief = SAMPLE_BRIEF, onDiscard, onPromote }) {
  const [checked, setChecked] = useState({});
  const [filter, setFilter] = useState("all");

  const items = brief.items || [];
  const filtered =
    filter === "all"
      ? items
      : items.filter((b) => (filter === "discard" ? !b.keep : b.keep));
  const selectedIds = Object.entries(checked)
    .filter(([, v]) => v)
    .map(([k]) => parseInt(k, 10));
  const allFilteredSelected =
    filtered.length > 0 && filtered.every((b) => checked[b.id]);

  const toggle = (id) => setChecked((c) => ({ ...c, [id]: !c[id] }));
  const toggleAll = () => {
    const allSelected = allFilteredSelected;
    const update = {};
    filtered.forEach((b) => {
      update[b.id] = !allSelected;
    });
    setChecked((c) => ({ ...c, ...update }));
  };

  const handleDiscard = () => {
    if (onDiscard) onDiscard(selectedIds);
    else {
      navigator.clipboard.writeText(selectedIds.join(", "));
      alert(`Copy these IDs to Claude: discard_bookmarks([${selectedIds.join(", ")}])`);
    }
    setChecked({});
  };

  const handlePromote = () => {
    if (onPromote) onPromote(selectedIds);
    else {
      navigator.clipboard.writeText(selectedIds.join(", "));
      alert(`Copy these IDs to Claude: promote_bookmarks([${selectedIds.join(", ")}])`);
    }
    setChecked({});
  };

  const discardCount = items.filter((b) => !b.keep).length;
  const keepCount = items.filter((b) => b.keep).length;

  return (
    <div
      style={{
        fontFamily: "ui-sans-serif, system-ui, 'Segoe UI', sans-serif",
        maxWidth: 720,
        margin: "0 auto",
        padding: "20px 16px 100px",
        background: "var(--color-background-primary, #f7f5f2)",
        minHeight: "100vh",
        color: "var(--color-text-primary, #1c1917)",
      }}
    >
      {/* Header */}
      <header style={{ marginBottom: 20 }}>
        <h1
          style={{
            fontSize: 22,
            fontWeight: 600,
            letterSpacing: "-0.02em",
            margin: "0 0 6px",
            color: "var(--color-text-primary, #1c1917)",
          }}
        >
          Bookmark review
        </h1>
        <p
          style={{
            fontSize: 14,
            color: "var(--color-text-secondary, #78716c)",
            margin: 0,
            lineHeight: 1.5,
          }}
        >
          {brief.overview}
        </p>
        <p
          style={{
            fontSize: 13,
            color: "var(--color-text-tertiary, #a8a29e)",
            margin: "8px 0 0",
          }}
        >
          {items.length} items · {discardCount} suggested discard · {keepCount} suggested keep
        </p>
      </header>

      {/* Filter */}
      <div
        style={{
          display: "flex",
          gap: 6,
          marginBottom: 12,
        }}
      >
        {(["all", "discard", "keep"]).map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            style={{
              padding: "6px 14px",
              borderRadius: 8,
              border: "1px solid",
              borderColor:
                filter === t
                  ? "var(--color-border-brand, #78716c)"
                  : "var(--color-border-secondary, #e7e5e4)",
              background:
                filter === t
                  ? "var(--color-background-secondary, #e7e5e4)"
                  : "transparent",
              color:
                filter === t
                  ? "var(--color-text-primary, #1c1917)"
                  : "var(--color-text-secondary, #78716c)",
              fontSize: 13,
              fontWeight: filter === t ? 600 : 400,
              cursor: "pointer",
            }}
          >
            {TYPE_LABELS[t]}{" "}
            <span style={{ opacity: 0.8 }}>
              ({t === "all" ? items.length : t === "discard" ? discardCount : keepCount})
            </span>
          </button>
        ))}
      </div>

      {/* Select all */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "10px 14px",
          background: "var(--color-background-secondary, #fff)",
          borderRadius: 8,
          marginBottom: 8,
          border: "1px solid var(--color-border-secondary, #e7e5e4)",
        }}
      >
        <input
          type="checkbox"
          checked={allFilteredSelected}
          onChange={toggleAll}
          style={{ width: 18, height: 18, cursor: "pointer", accentColor: "#78716c" }}
        />
        <span
          style={{
            fontSize: 13,
            color: "var(--color-text-secondary, #78716c)",
            fontWeight: 500,
          }}
        >
          Select all in view ({filtered.length})
        </span>
      </div>

      {/* List */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {filtered.map((b) => (
          <article
            key={b.id}
            onClick={() => toggle(b.id)}
            style={{
              padding: "14px 16px",
              background: checked[b.id]
                ? "var(--color-background-selected, #fef3c7)"
                : "var(--color-background-secondary, #fff)",
              borderRadius: 10,
              border: `1px solid ${
                checked[b.id]
                  ? "var(--color-border-selected, #fcd34d)"
                  : "var(--color-border-secondary, #e7e5e4)"
              }`,
              cursor: "pointer",
              transition: "background 0.15s, border-color 0.15s",
            }}
          >
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              <input
                type="checkbox"
                checked={!!checked[b.id]}
                onChange={() => toggle(b.id)}
                onClick={(e) => e.stopPropagation()}
                style={{
                  width: 18,
                  height: 18,
                  marginTop: 2,
                  cursor: "pointer",
                  flexShrink: 0,
                  accentColor: "#78716c",
                }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 4,
                  }}
                >
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      padding: "2px 8px",
                      borderRadius: 6,
                      background: b.keep ? "#dcfce7" : "#fee2e2",
                      color: b.keep ? "#166534" : "#991b1b",
                      textTransform: "uppercase",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {b.keep ? "Keep" : "Discard"}
                  </span>
                  <span
                    style={{
                      fontSize: 15,
                      fontWeight: 600,
                      color: "var(--color-text-primary, #1c1917)",
                    }}
                  >
                    {b.title || "(no title)"}
                  </span>
                </div>
                <p
                  style={{
                    fontSize: 14,
                    color: "var(--color-text-secondary, #57534e)",
                    margin: "4px 0 8px",
                    lineHeight: 1.5,
                  }}
                >
                  {b.summary}
                </p>
                {b.key_points?.length > 0 && (
                  <ul
                    style={{
                      margin: "0 0 8px",
                      paddingLeft: 18,
                      fontSize: 13,
                      color: "var(--color-text-tertiary, #78716c)",
                      lineHeight: 1.5,
                    }}
                  >
                    {b.key_points.map((pt, i) => (
                      <li key={i}>{pt}</li>
                    ))}
                  </ul>
                )}
                <a
                  href={b.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  style={{
                    fontSize: 12,
                    color: "var(--color-text-link, #78716c)",
                    textDecoration: "underline",
                    wordBreak: "break-all",
                  }}
                >
                  {b.url.length > 70 ? b.url.slice(0, 70) + "…" : b.url}
                </a>
              </div>
              <span
                style={{
                  fontSize: 11,
                  color: "var(--color-text-tertiary, #a8a29e)",
                  flexShrink: 0,
                }}
              >
                #{b.id}
              </span>
            </div>
          </article>
        ))}
      </div>

      {/* Action bar */}
      {selectedIds.length > 0 && (
        <div
          style={{
            position: "fixed",
            bottom: 0,
            left: 0,
            right: 0,
            background: "var(--color-background-primary, #1c1917)",
            color: "var(--color-text-inverse, #fafaf9)",
            padding: "14px 20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            boxShadow: "0 -4px 20px rgba(0,0,0,0.15)",
            zIndex: 100,
          }}
        >
          <span style={{ fontSize: 14 }}>
            <strong>{selectedIds.length}</strong> selected
          </span>
          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={() => setChecked({})}
              style={{
                padding: "8px 16px",
                borderRadius: 8,
                border: "1px solid rgba(255,255,255,0.3)",
                background: "transparent",
                color: "inherit",
                cursor: "pointer",
                fontSize: 13,
              }}
            >
              Clear
            </button>
            <button
              onClick={handlePromote}
              style={{
                padding: "8px 16px",
                borderRadius: 8,
                border: "none",
                background: "#4d7c0f",
                color: "white",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              Promote ({selectedIds.length})
            </button>
            <button
              onClick={handleDiscard}
              style={{
                padding: "8px 16px",
                borderRadius: 8,
                border: "none",
                background: "#b91c1c",
                color: "white",
                cursor: "pointer",
                fontSize: 13,
                fontWeight: 600,
              }}
            >
              Discard ({selectedIds.length})
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
