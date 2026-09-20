import { SIGNUP_STEPS } from "./signupConstants";

export default function SignupProgress({ step }) {
  return (
    <div style={{ marginBottom: "28px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: "8px",
        }}
      >
        {SIGNUP_STEPS.map((label, index) => (
          <span
            key={label}
            style={{
              fontSize: "11px",
              fontWeight: index <= step ? 700 : 400,
              color:
                index < step
                  ? "#0070C0"
                  : index === step
                    ? "#001F5B"
                    : "#9ca3af",
            }}
          >
            {label}
          </span>
        ))}
      </div>
      <div
        style={{
          height: "4px",
          background: "#e5e7eb",
          borderRadius: "99px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${((step + 1) / SIGNUP_STEPS.length) * 100}%`,
            background: "linear-gradient(90deg, #001F5B, #0070C0)",
            borderRadius: "99px",
            transition: "width 0.3s ease",
          }}
        />
      </div>
    </div>
  );
}
