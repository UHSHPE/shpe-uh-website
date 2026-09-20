export function SignupRow({ label, required, error, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
      <label style={{ fontSize: "13px", fontWeight: 600, color: "#374151" }}>
        {label}
        {required && (
          <span style={{ color: error ? "#D33A02" : "#6b7280" }}> *</span>
        )}
      </label>
      {children}
      {error && (
        <p
          style={{
            margin: 0,
            fontSize: "12px",
            color: "#D33A02",
            fontWeight: 500,
          }}
        >
          {error}
        </p>
      )}
    </div>
  );
}

export function Toggle({ value, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      style={{
        width: "48px",
        height: "26px",
        borderRadius: "99px",
        background: value ? "#0070C0" : "#d1d5db",
        border: "none",
        cursor: "pointer",
        position: "relative",
        transition: "background 0.2s",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: "3px",
          left: value ? "24px" : "3px",
          width: "20px",
          height: "20px",
          borderRadius: "50%",
          background: "#fff",
          transition: "left 0.2s",
          boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
        }}
      />
    </button>
  );
}

export function MultiCheck({ options, selected, onToggle }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "6px",
        maxHeight: "180px",
        overflowY: "auto",
        padding: "4px 0",
      }}
    >
      {options.map((option) => (
        <label
          key={option}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "13px",
            cursor: "pointer",
          }}
        >
          <input
            type="checkbox"
            checked={selected.includes(option)}
            onChange={() => onToggle(option)}
            style={{ accentColor: "#0070C0", width: "15px", height: "15px" }}
          />
          {option}
        </label>
      ))}
    </div>
  );
}
