import { useRef } from "react";
import { CloseIcon, ImageIcon } from "../shopIcons";
import { formLabel } from "./styles";

import { APPAREL_SIZES } from "./productFormConstants";

export default function ProductFormModal({ form, setForm, onSave }) {
  const fileInputRef = useRef(null);
  const valid =
    form.name.trim() !== "" &&
    form.price.trim() !== "" &&
    !Number.isNaN(parseFloat(form.price));
  const update = (changes) => setForm({ ...form, ...changes });

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(3,10,30,.45)",
        zIndex: 3200,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "40px 16px",
        overflowY: "auto",
        animation: "shopFadeIn .2s ease",
      }}
      onClick={() => setForm(null)}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          width: "540px",
          maxWidth: "100%",
          background: "#fff",
          borderRadius: "18px",
          boxShadow: "var(--shadow-modal)",
          animation: "shopRiseIn .25s ease",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "20px 24px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <h3
            style={{
              margin: 0,
              fontSize: "18px",
              fontWeight: 800,
              color: "var(--ink)",
            }}
          >
            {form.id ? "Edit product" : "Add product"}
          </h3>
          <button
            onClick={() => setForm(null)}
            aria-label="Close"
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "999px",
              border: "none",
              background: "var(--surface-soft)",
              color: "var(--ink-soft)",
              cursor: "pointer",
              display: "grid",
              placeItems: "center",
            }}
          >
            <CloseIcon size={16} />
          </button>
        </div>

        <div
          style={{
            padding: "22px 24px",
            display: "flex",
            flexDirection: "column",
            gap: "16px",
          }}
        >
          <label style={formLabel}>
            Name
            <input
              className="shopInput"
              value={form.name}
              onChange={(event) => update({ name: event.target.value })}
              placeholder="e.g. SHPE UH Quarter-Zip"
            />
          </label>
          <label style={formLabel}>
            Description
            <textarea
              className="shopInput"
              rows={3}
              value={form.description}
              onChange={(event) => update({ description: event.target.value })}
              placeholder="Short description buyers will see"
              style={{ resize: "vertical" }}
            />
          </label>
          <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
            <label style={{ ...formLabel, flex: 1, minWidth: "120px" }}>
              Price (USD)
              <input
                className="shopInput"
                inputMode="decimal"
                value={form.price}
                onChange={(event) => update({ price: event.target.value })}
                placeholder="45"
              />
            </label>
            <div style={{ ...formLabel, flex: 1, minWidth: "170px" }}>
              Product type
              <div style={{ display: "flex", gap: "8px" }}>
                {[
                  { value: "apparel", label: "Apparel" },
                  { value: "item", label: "Sticker / item" },
                ].map((type) => {
                  const active = form.product_type === type.value;
                  return (
                    <button
                      key={type.value}
                      onClick={() => update({ product_type: type.value })}
                      style={{
                        flex: 1,
                        borderRadius: "10px",
                        padding: "10px",
                        fontSize: "13px",
                        fontWeight: active ? 700 : 600,
                        border: active
                          ? "1.5px solid var(--shpe-blue)"
                          : "1.5px solid var(--border)",
                        background: active ? "var(--surface-tint)" : "#fff",
                        color: active ? "var(--shpe-blue)" : "var(--ink-soft)",
                        cursor: "pointer",
                      }}
                    >
                      {type.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {form.product_type === "apparel" && (
            <div style={formLabel}>
              Available sizes
              <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                {APPAREL_SIZES.map((size) => {
                  const active = form.sizes.includes(size);
                  return (
                    <button
                      key={size}
                      onClick={() =>
                        update({
                          sizes: active
                            ? form.sizes.filter((item) => item !== size)
                            : [...form.sizes, size],
                        })
                      }
                      style={{
                        minWidth: "46px",
                        borderRadius: "9px",
                        padding: "8px 10px",
                        fontSize: "13px",
                        fontWeight: active ? 700 : 600,
                        border: active
                          ? "1.5px solid var(--shpe-blue)"
                          : "1.5px solid var(--border)",
                        background: active ? "var(--shpe-blue)" : "#fff",
                        color: active ? "#fff" : "var(--ink-soft)",
                        cursor: "pointer",
                      }}
                    >
                      {size}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div style={formLabel}>
            Product image
            <div
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: "1.5px dashed #CBD5E4",
                borderRadius: "12px",
                padding: "22px",
                textAlign: "center",
                background: "var(--surface-muted)",
                cursor: "pointer",
              }}
            >
              <ImageIcon
                size={24}
                stroke="var(--muted-soft)"
                style={{ marginBottom: "6px" }}
              />
              <p
                style={{
                  margin: 0,
                  fontSize: "13px",
                  color: "var(--muted)",
                  fontWeight: 400,
                }}
              >
                <strong style={{ color: "var(--shpe-blue)" }}>
                  {form.imageFile ? form.imageFile.name : "Upload an image"}
                </strong>
                {!form.imageFile && " · PNG, JPG, WebP"}
              </p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={(event) =>
                update({ imageFile: event.target.files?.[0] ?? null })
              }
              style={{ display: "none" }}
            />
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "12px",
              border: "1px solid var(--border)",
              borderRadius: "10px",
              padding: "12px 14px",
            }}
          >
            <div>
              <p
                style={{
                  margin: 0,
                  fontSize: "13px",
                  fontWeight: 700,
                  color: "var(--ink)",
                }}
              >
                Availability
              </p>
              <p
                style={{
                  margin: "2px 0 0",
                  fontSize: "12px",
                  color: "var(--muted)",
                }}
              >
                {form.is_active
                  ? "Visible in the shop"
                  : "Hidden from the shop"}
              </p>
            </div>
            <button
              onClick={() => update({ is_active: !form.is_active })}
              aria-label="Toggle availability"
              style={{
                width: "46px",
                height: "26px",
                borderRadius: "999px",
                border: "none",
                background: form.is_active
                  ? "var(--shpe-blue)"
                  : "var(--border-strong)",
                cursor: "pointer",
                position: "relative",
                flexShrink: 0,
              }}
            >
              <span
                style={{
                  position: "absolute",
                  top: "3px",
                  [form.is_active ? "right" : "left"]: "3px",
                  width: "20px",
                  height: "20px",
                  borderRadius: "999px",
                  background: "#fff",
                }}
              />
            </button>
          </div>
        </div>
        <div
          style={{
            display: "flex",
            gap: "10px",
            justifyContent: "flex-end",
            padding: "16px 24px",
            borderTop: "1px solid var(--border)",
          }}
        >
          <button
            onClick={() => setForm(null)}
            style={{
              borderRadius: "999px",
              padding: "10px 20px",
              fontSize: "14px",
              fontWeight: 700,
              border: "1px solid var(--border-strong)",
              background: "#fff",
              color: "var(--ink)",
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            className="primaryBtn"
            disabled={!valid}
            onClick={onSave}
            style={{ padding: "10px 22px", fontSize: "14px" }}
          >
            Save product
          </button>
        </div>
      </div>
    </div>
  );
}
