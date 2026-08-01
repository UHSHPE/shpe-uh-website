/* eslint-disable no-unused-vars */
import { motion } from "framer-motion";

// Success mark for the mobile check-in flow (design handoff §2 —
// okCircle / okCheck / softPulse keyframes, ~1.6s total, reimplemented in
// Framer Motion to match the site's existing reveal conventions instead of
// the raw CSS @keyframes the design board used).
const EASE = [0.22, 1, 0.36, 1];

export default function CheckInSuccess({ size = 120 }) {
  return (
    <div style={{ position: "relative", width: size, height: size, display: "grid", placeItems: "center" }}>
      {/* softPulse: ambient halo, alternating scale/opacity, loops forever */}
      <motion.div
        aria-hidden="true"
        style={{ position: "absolute", inset: -18, borderRadius: "999px", background: "rgba(255,255,255,.15)" }}
        animate={{ scale: [0.9, 1.06], opacity: [0.35, 1] }}
        transition={{ duration: 1.6, repeat: Infinity, repeatType: "reverse", ease: EASE }}
      />
      {/* okCircle: scale/opacity in, hold, out over ~1.6s total */}
      <motion.svg
        width={size}
        height={size}
        viewBox="0 0 120 120"
        role="img"
        aria-label="Checked in"
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: [0.6, 1, 1, 0.6], opacity: [0, 1, 1, 0] }}
        transition={{ duration: 1.6, times: [0, 0.14, 0.9, 1], ease: EASE }}
      >
        <circle cx="60" cy="60" r="56" fill="#fff" />
        {/* okCheck: stroke-dash reveal between 12% and 34% of the timeline,
            framer's pathLength is the direct equivalent of stroke-dashoffset */}
        <motion.path
          d="M35 62 L52 79 L87 41"
          fill="none"
          stroke="var(--shpe-navy)"
          strokeWidth="9"
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.35, delay: 0.19, ease: EASE }}
        />
      </motion.svg>
    </div>
  );
}
