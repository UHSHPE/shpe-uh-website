export const columnStyle = {
  display: "flex",
  flexDirection: "column",
  gap: "16px",
};

export const inputStyle = {
  padding: "10px 14px",
  borderRadius: "8px",
  border: "1.5px solid #d1d5db",
  fontSize: "14px",
  outline: "none",
  fontFamily: "Work Sans, sans-serif",
  width: "100%",
  boxSizing: "border-box",
};

export function fieldStyle(error) {
  return {
    ...inputStyle,
    border: `1.5px solid ${error ? "#D33A02" : "#d1d5db"}`,
  };
}
