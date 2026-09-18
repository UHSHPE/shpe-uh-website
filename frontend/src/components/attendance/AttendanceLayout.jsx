/* eslint-disable no-unused-vars */
import { motion } from "framer-motion";

const EASE = [0.22, 1, 0.36, 1];

export function AttendanceShell({ flat, children }) {
  return (
    <div
      style={{
        minHeight: "100dvh",
        background: flat ? "#003A70" : "var(--gradient-navy)",
        color: "#fff",
        display: "flex",
        flexDirection: "column",
        fontFamily: "var(--font-body)",
      }}
    >
      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: "flex",
          flexDirection: "column",
          padding: "0 24px 40px",
        }}
      >
        {children}
      </div>
    </div>
  );
}

export function Reveal({ delay = 0, children, style }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: EASE }}
      style={style}
    >
      {children}
    </motion.div>
  );
}

export function PrimaryCta({ children, disabled, ...props }) {
  return (
    <button
      type="button"
      disabled={disabled}
      {...props}
      style={{
        width: "100%",
        height: "56px",
        borderRadius: "999px",
        background: "#fff",
        color: "var(--shpe-navy)",
        border: "none",
        fontSize: "17px",
        fontWeight: 700,
        fontFamily: "inherit",
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.6 : 1,
        boxShadow: "0 4px 30px rgba(0,31,91,.25)",
      }}
    >
      {children}
    </button>
  );
}

export function AttendanceSpinner({ caption }) {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "28px",
      }}
    >
      <div
        style={{
          width: "64px",
          height: "64px",
          borderRadius: "999px",
          border: "3px solid rgba(255,255,255,.25)",
          borderTopColor: "#fff",
          animation: "shopSpin .9s linear infinite",
        }}
      />
      <p
        style={{
          margin: 0,
          fontSize: "17px",
          lineHeight: 1.45,
          fontWeight: 500,
          color: "rgba(255,255,255,.8)",
        }}
      >
        {caption}
      </p>
    </div>
  );
}
