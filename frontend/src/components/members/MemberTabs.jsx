const TABS = [
  { key: "all", label: "All" },
  { key: "eboard", label: "E-Board" },
  { key: "chairs", label: "Chairs" },
  { key: "structure", label: "Structure" },
];

export default function MemberTabs({ activeTab, counts, onChange }) {
  return (
    <div
      style={{
        display: "flex",
        gap: "4px",
        borderBottom: "1px solid var(--border)",
        flexWrap: "wrap",
        marginBottom: "18px",
      }}
    >
      {TABS.map((tab) => {
        const active = activeTab === tab.key;
        const count = counts[tab.key];
        return (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            style={{
              position: "relative",
              border: "none",
              background: "transparent",
              padding: "10px 14px 14px",
              fontSize: "14px",
              fontFamily: "inherit",
              fontWeight: active ? 700 : 600,
              color: active ? "var(--shpe-blue)" : "var(--muted)",
              cursor: "pointer",
            }}
          >
            {tab.label}
            {count !== undefined && (
              <span
                style={{
                  marginLeft: "7px",
                  background: active
                    ? "var(--shpe-blue)"
                    : "var(--surface-soft)",
                  color: active ? "#fff" : "var(--muted)",
                  borderRadius: "999px",
                  padding: "1px 7px",
                  fontSize: "11px",
                }}
              >
                {count}
              </span>
            )}
            {active && (
              <span
                style={{
                  position: "absolute",
                  left: "8px",
                  right: "8px",
                  bottom: 0,
                  height: "2px",
                  background: "var(--shpe-blue)",
                  borderRadius: "999px",
                }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
