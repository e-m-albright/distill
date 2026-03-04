/**
 * Quick Pass UI — title/URL review before distill.
 *
 * Data shape: { items: [{ id, title, url }], category?: string }
 * Matches list_bookmarks output. Type badges inferred from URL patterns.
 *
 * Use for the quick discard pass: review by title/URL, discard obvious junk,
 * then run distill on survivors.
 */
import { useState, useMemo } from "react";

function inferType(url, title) {
  const u = (url || "").toLowerCase();
  const t = (title || "").toLowerCase();
  if (u.includes("google.com/search")) return "Google Search";
  if (u.includes("youtube.com/shorts") || u.includes("m.youtube.com/shorts")) return "YouTube Short";
  if (u.includes("youtube.com/watch") || u.includes("m.youtube.com/watch")) return "YouTube";
  if (u.includes("checkout") || u.includes("/cart") || u.includes("thank-you") || u.includes("/register")) return "Checkout/Cart";
  if (!t || t === "(no title)" || t.trim() === "" || t === url) return "Untitled";
  return "Article/Other";
}

// Sample data matching list_bookmarks output (for demo; MCP would pass via ontoolresult)
const SAMPLE_ITEMS = [
  { id: 387, title: "plato books", url: "https://www.google.com/search?q=plato+books" },
  { id: 388, title: "voltaire books", url: "https://www.google.com/search?q=voltaire+books" },
  { id: 420, title: "nyt spiked cider", url: "https://www.google.com/search?q=nyt+spiked+cider" },
  { id: 384, title: "(no title)", url: "https://m.youtube.com/shorts/Pp0xRjkiIII" },
  { id: 419, title: "(no title)", url: "https://m.youtube.com/shorts/XRPPuJ5nggM" },
  { id: 684, title: "Big Bluff Ranch Checkout", url: "https://www.bigbluffranch.com/checkout?cartToken=..." },
  { id: 616, title: "LaserAway Thank You page", url: "https://www.laseraway.com/thank-you/" },
  { id: 562, title: "ministry for the future obama", url: "https://www.google.com/search?q=the+ministry+for+the+future+obama" },
  { id: 465, title: "https://www.fool.com/investing/2025/10/17/once-in-decade-investment/", url: "https://www.fool.com/investing/2025/10/17/once-in-decade-investment/" },
];

const TYPE_ORDER = ["All", "Google Search", "YouTube Short", "YouTube", "Checkout/Cart", "Untitled", "Article/Other"];

export default function QuickPass({ items = SAMPLE_ITEMS, category, onDiscard }) {
  const [checked, setChecked] = useState({});
  const [filter, setFilter] = useState("All");

  const itemsWithType = useMemo(
    () => items.map((b) => ({ ...b, type: inferType(b.url, b.title) })),
    [items]
  );

  const typeCounts = useMemo(() => {
    const counts = { All: itemsWithType.length };
    itemsWithType.forEach((b) => {
      counts[b.type] = (counts[b.type] || 0) + 1;
    });
    return counts;
  }, [itemsWithType]);

  const filtered =
    filter === "All"
      ? itemsWithType
      : itemsWithType.filter((b) => b.type === filter);

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
      alert(
        `Copied ${selectedIds.length} IDs to clipboard:\n${selectedIds.join(", ")}\n\nPaste these back to Claude to confirm discard.`
      );
    }
    setChecked({});
  };

  return (
    <div
      style={{
        fontFamily: "ui-sans-serif, system-ui, 'Segoe UI', sans-serif",
        maxWidth: 780,
        margin: "0 auto",
        padding: "24px 16px 100px",
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
          Quick pass — discard by title/URL
        </h1>
        <p
          style={{
            fontSize: 14,
            color: "var(--color-text-secondary, #78716c)",
            margin: 0,
            lineHeight: 1.5,
          }}
        >
          {itemsWithType.length} bookmarks
          {category ? ` in ${category}` : ""} · {selectedIds.length} selected for discard
        </p>
        <p
          style={{
            fontSize: 13,
            color: "var(--color-text-tertiary, #a8a29e)",
            margin: "6px 0 0",
          }}
        >
          Remove obvious junk, then run distill on survivors.
        </p>
      </header>

      {/* Filter tabs */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          marginBottom: 16,
        }}
      >
        {TYPE_ORDER.filter((t) => t === "All" || (typeCounts[t] || 0) > 0).map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            style={{
              padding: "6px 14px",
              borderRadius: 20,
              border: "1px solid",
              borderColor: filter === t ? "#78716c" : "#e7e5e4",
              background: filter === t ? "#e7e5e4" : "transparent",
              color: filter === t ? "#1c1917" : "#78716c",
              fontSize: 13,
              fontWeight: filter === t ? 600 : 400,
              cursor: "pointer",
            }}
          >
            {t} <span style={{ opacity: 0.8 }}>({typeCounts[t] || 0})</span>
          </button>
        ))}
      </div>

      {/* Select all row */}
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
          style={{
            width: 18,
            height: 18,
            cursor: "pointer",
            accentColor: "#78716c",
          }}
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

      {/* Bookmark list */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {filtered.map((b) => (
          <div
            key={b.id}
            onClick={() => toggle(b.id)}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 12,
              padding: "12px 16px",
              background: checked[b.id] ? "#fef2f2" : "var(--color-background-secondary, #fff)",
              borderRadius: 10,
              border: `1px solid ${checked[b.id] ? "#fca5a5" : "#e7e5e4"}`,
              cursor: "pointer",
              transition: "all 0.1s",
            }}
          >
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
                    borderRadius: 10,
                    background: "#f5f5f4",
                    color: "#57534e",
                    whiteSpace: "nowrap",
                  }}
                >
                  {b.type}
                </span>
                <span
                  style={{
                    fontSize: 15,
                    fontWeight: 500,
                    color: "var(--color-text-primary, #1c1917)",
                  }}
                >
                  {b.title || "(no title)"}
                </span>
              </div>
              <a
                href={b.url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                style={{
                  fontSize: 12,
                  color: "#78716c",
                  wordBreak: "break-all",
                  textDecoration: "underline",
                }}
              >
                {b.url.length > 90 ? b.url.slice(0, 90) + "…" : b.url}
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
            background: "#1c1917",
            color: "#fafaf9",
            padding: "14px 20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            boxShadow: "0 -4px 20px rgba(0,0,0,0.15)",
            zIndex: 100,
          }}
        >
          <span style={{ fontSize: 14 }}>
            <strong>{selectedIds.length}</strong> selected for discard
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
              Confirm discard ({selectedIds.length})
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
