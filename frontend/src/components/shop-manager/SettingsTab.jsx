import { formLabel } from "./styles";

export default function SettingsTab({ draft, setDraft, onSave }) {
  const cap = parseInt(draft.order_item_cap, 10);
  const valid = draft.tagline.trim() !== "" && cap > 0;

  return (
    <div
      style={{
        maxWidth: "560px",
        display: "flex",
        flexDirection: "column",
        gap: "16px",
      }}
    >
      <p style={{ margin: 0, fontSize: "14px", color: "var(--muted)" }}>
        Storefront copy and order limits — changes apply immediately.
      </p>
      <label style={formLabel}>
        Storefront tagline
        <textarea
          className="shopInput"
          rows={2}
          value={draft.tagline}
          onChange={(event) =>
            setDraft({ ...draft, tagline: event.target.value })
          }
          placeholder="Shown under the shop hero heading"
          style={{ resize: "vertical" }}
        />
      </label>
      <label style={{ ...formLabel, maxWidth: "220px" }}>
        Max units per item per order
        <input
          className="shopInput"
          inputMode="numeric"
          value={draft.order_item_cap}
          onChange={(event) =>
            setDraft({ ...draft, order_item_cap: event.target.value })
          }
          placeholder="5"
        />
      </label>
      <button
        className="primaryBtn"
        disabled={!valid}
        onClick={onSave}
        style={{
          alignSelf: "flex-start",
          padding: "10px 22px",
          fontSize: "14px",
        }}
      >
        Save settings
      </button>
    </div>
  );
}
