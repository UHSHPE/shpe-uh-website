import { productImageUrl } from "../api/api";

// Product photo, or the design's hatched placeholder with a mono label chip
// while no real merch photos exist.
export default function ProductImage({ product, label, aspectRatio = "4/3", radius = 0, labelSize = 11 }) {
  const url = productImageUrl(product);

  if (url) {
    return (
      <img
        src={url}
        alt={product.name}
        style={{
          width: "100%",
          aspectRatio,
          objectFit: "cover",
          display: "block",
          borderRadius: radius,
        }}
      />
    );
  }

  return (
    <div
      style={{
        aspectRatio,
        background: "var(--placeholder-hatch)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: radius,
      }}
    >
      <span
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: labelSize,
          color: "#5b6b85",
          background: "rgba(255,255,255,.8)",
          border: "1px solid #dbe4f0",
          borderRadius: "6px",
          padding: "4px 9px",
          maxWidth: "82%",
          textAlign: "center",
        }}
      >
        {label ?? product.name}
      </span>
    </div>
  );
}
