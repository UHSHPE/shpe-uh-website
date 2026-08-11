import { useNavigate } from "react-router-dom"
import confetti from "../assets/membershpeImages/confettiBackground.png"
import shpeSpirit from "../assets/images/SHPESpiritWeb.png"
import useDocumentTitle from "../hooks/useDocumentTitle"

export function Hero() {
  return (
    <div className="relative w-full min-h-screen overflow-clip">
      <img
        src={confetti}
        alt="Confetti background"
        className="absolute block top-25 w-full h-full object-cover"
      />
      <div
        className="relative z-10 flex flex-col min-h-screen items-center justify-center gap-7"
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "Work Sans, sans-serif"

        }}
      >
        <h1 className="mt-12 z-10 flex flex-col items-center bg-white px-4">
          <span
            className="px-5 -mb-2 -mt-4 md:-mt-10 text-[clamp(3rem,10vw,9rem)] font-bold leading-none"
            style={{
              backgroundImage: `linear-gradient(rgba(211,58,2,0.95), rgba(211,58,2,0.95)), url(${shpeSpirit})`,
              backgroundBlendMode: 'multiply',
              backgroundSize: 'cover',
              backgroundPosition: 'center center',
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              color: "transparent",
              WebkitTextFillColor: "transparent",
            }}
          >
            Bienvenidos
          </span>
          <span
            className="px-4 pb-2"
            style={{
              fontFamily: "Work Sans, sans-serif",
              color: "#1A2858",
              textAlign: 'center',
              textShadow: "0 1px 1px rgba(0, 0, 0, 0.25)",
              fontSize: "clamp(2rem, 6vw, 5rem)",
              fontStyle: "normal",
              fontWeight: 500,
              lineHeight: "normal",
              letterSpacing: "2px",
            }}
          >
            to the familia!
          </span>
        </h1>

        <p
          className="max-w-[90%] md:max-w-[70%] bg-white px-4 py-3"
          style={{
            fontFamily: "Work Sans, sans-serif",
            color: "#1A2858",
            textAlign: 'center',
            fontSize: "clamp(1rem, 2.2vw, 1.875rem)",
            fontStyle: "normal",
            fontWeight: 500,
            lineHeight: 1.35,
            letterSpacing: "-0.72px",
          }}
        >
          SHPE is the source for quality Hispanic engineers and technical talent. While you may not be Hispanic or an engineer, you can still join and take advantage of the benefits and opportunities offered by SHPE at the national and local levels.
        </p>
      </div>
    </div>
  );
}

/* ================================================================
   WHY JOIN — two clear, readable membership tiers on a soft surface.
   Same information as before, restructured into brand-clean cards.
   ================================================================ */
function Check({ color }) {
  return (
    <span
      aria-hidden="true"
      style={{
        flexShrink: 0,
        marginTop: 2,
        width: 20,
        height: 20,
        borderRadius: "var(--radius-pill)",
        background: `color-mix(in srgb, ${color} 15%, #fff)`,
        color,
        display: "grid",
        placeItems: "center",
        fontSize: 12,
        fontWeight: 800,
        lineHeight: 1,
      }}
    >
      ✓
    </span>
  );
}

function Benefit({ title, desc, color }) {
  return (
    <li style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
      <Check color={color} />
      <span style={{ lineHeight: 1.45 }}>
        <strong style={{ fontWeight: 600, color: "var(--shpe-navy)" }}>{title}</strong>
        {desc && <span style={{ color: "var(--muted)" }}> — {desc}</span>}
      </span>
    </li>
  );
}

// CTA matching the design-system Button variants used in the handoff:
//   accent → SHPE red, radius 20px;  bright → SHPE blue-bright, pill.
function CtaButton({ variant, children, onClick }) {
  const accent = variant === "bright";
  return (
    <button
      onClick={onClick}
      style={{
        marginTop: 24,
        width: "100%",
        padding: "15px 24px",
        border: "none",
        cursor: "pointer",
        fontFamily: "var(--font-body)",
        fontWeight: 700,
        fontSize: 16,
        color: "#fff",
        background: accent ? "var(--shpe-blue-bright)" : "var(--shpe-red)",
        borderRadius: accent ? "var(--radius-pill)" : "var(--radius-2xl)",
        transition: "filter 0.15s var(--ease-out), transform 0.05s var(--ease-out)",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.filter = "brightness(0.95)")}
      onMouseLeave={(e) => (e.currentTarget.style.filter = "none")}
      onMouseDown={(e) => (e.currentTarget.style.transform = "translateY(1px)")}
      onMouseUp={(e) => (e.currentTarget.style.transform = "none")}
    >
      {children}
    </button>
  );
}

function TierCard({ accent, eyebrow, price, period, title, lead, children, cta, ctaVariant, onCta }) {
  return (
    <div
      style={{
        position: "relative",
        flex: "1 1 380px",
        maxWidth: 540,
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-xl)",
        boxShadow: "var(--shadow-card)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div style={{ height: 5, background: accent }} />
      <div style={{ padding: "30px 30px 32px", display: "flex", flexDirection: "column", flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <span style={{ textTransform: "uppercase", letterSpacing: "0.1em", fontSize: 11, fontWeight: 700, color: accent }}>
            {eyebrow}
          </span>
          <span style={{ display: "flex", alignItems: "baseline", gap: 5, color: "var(--shpe-navy)" }}>
            <span style={{ fontSize: 28, fontWeight: 800, letterSpacing: "-0.5px" }}>{price}</span>
            <span style={{ fontSize: 13, fontWeight: 500, color: "var(--muted)" }}>/ {period}</span>
          </span>
        </div>

        <h3 style={{ margin: "14px 0 0", color: "var(--shpe-navy)", fontSize: 24, fontWeight: 700, lineHeight: 1.15 }}>
          {title}
        </h3>
        {lead && <p style={{ margin: "10px 0 0", color: "var(--ink-soft)", fontSize: 15, lineHeight: 1.55 }}>{lead}</p>}

        <div style={{ flex: 1 }}>{children}</div>

        <CtaButton variant={ctaVariant} onClick={onCta}>{cta}</CtaButton>
      </div>
    </div>
  );
}

export function JoinSecton() {
  const navigate = useNavigate();
  const goSignup = () => navigate("/signup");
  const goNational = () =>
    window.open(
      "https://www.shpeconnect.org/eweb/DynamicPage.aspx?WebCode=LoginRequired&expires=yes&Site=shpe",
      "_blank",
      "noopener,noreferrer"
    );

  return (
    <section
      style={{
        background: "var(--surface-muted)",
        borderTop: "1px solid var(--border)",
        borderBottom: "1px solid var(--border)",
        padding: "clamp(56px, 8vw, 100px) 24px",
        fontFamily: "var(--font-body)",
      }}
    >
      <div style={{ maxWidth: "var(--container-xl)", margin: "0 auto" }}>
        {/* header */}
        <div style={{ textAlign: "center", maxWidth: 760, margin: "0 auto 48px" }}>
          <p style={{ margin: 0, textTransform: "uppercase", letterSpacing: "0.14em", fontSize: 13, fontWeight: 700, color: "var(--shpe-red)" }}>
            Membership
          </p>
          <h2 style={{ margin: "12px 0 0", color: "var(--shpe-navy)", fontWeight: 700, fontSize: "clamp(34px, 5vw, 56px)", lineHeight: 1.04, letterSpacing: "-0.5px" }}>
            Why Join SHPE?
          </h2>
          <p style={{ margin: "18px 0 0", color: "var(--ink-soft)", fontSize: 18, lineHeight: 1.55 }}>
            Two ways to belong — and they stack. Join the chapter for the day-to-day familia,
            then go national to unlock SHPE-wide resources, scholarships, and conferences.
          </p>
        </div>

        {/* tiers */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 28, justifyContent: "center", alignItems: "stretch" }}>
          <TierCard
            accent="var(--shpe-orange)"
            eyebrow="Chapter"
            price="$20"
            period="academic year"
            title="T-Shirt Dues"
            lead="Being a part of SHPE at UH includes the following benefits:"
            cta="Join Now"
            ctaVariant="accent"
            onCta={goSignup}
          >
            <ul style={{ listStyle: "none", margin: "22px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: 14, fontSize: 15 }}>
              <Benefit color="var(--shpe-orange)" title="Access to our Slack" desc="where announcements drop first and opportunities are shared with members" />
              <Benefit color="var(--shpe-orange)" title="Eligibility for MemberSHPE Awards" desc="around $10,000 is awarded every year" />
              <Benefit color="var(--shpe-orange)" title="Internship / Co-Op Database" />
              <Benefit color="var(--shpe-orange)" title="Professional Development" desc="resume critiques, mock interviews, and networking events" />
              <Benefit color="var(--shpe-orange)" title="MentorSHPE Program" />
              <Benefit color="var(--shpe-orange)" title="Resume Book" desc="shared directly with our corporate sponsors" />
              <Benefit color="var(--shpe-orange)" title="SHPE Graduation Stole" />
              <Benefit color="var(--shpe-orange)" title="Chapter Shirt" />
            </ul>
          </TierCard>

          <TierCard
            accent="var(--shpe-blue-bright)"
            eyebrow="SHPE National"
            price="$10"
            period="year"
            title="National MemberSHPE"
            lead="Become an official member under SHPE National and represent UH beyond campus."
            cta="Become a National Member"
            ctaVariant="bright"
            onCta={goNational}
          >
            <ul style={{ listStyle: "none", margin: "22px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: 14, fontSize: 15 }}>
              <Benefit color="var(--shpe-blue-bright)" title="National resources & scholarships" desc="member-only support across the SHPE network" />
              <Benefit color="var(--shpe-blue-bright)" title="Conference access" desc="attend RLDC (Regional Leadership Development Conference) and National Convention" />
              <Benefit color="var(--shpe-blue-bright)" title="Official SHPE National standing" desc="recognized membership that follows you after graduation" />
            </ul>

            <div
              style={{
                marginTop: 22,
                padding: "16px 18px",
                background: "var(--surface-tint)",
                border: "1px solid color-mix(in srgb, var(--shpe-blue-bright) 24%, #fff)",
                borderRadius: "var(--radius-md)",
              }}
            >
              <p style={{ margin: 0, fontSize: 12, fontWeight: 700, color: "var(--shpe-blue)", textTransform: "uppercase", letterSpacing: "0.07em" }}>
                When you register, you'll be asked:
              </p>
              <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 5, fontSize: 14, color: "var(--ink-soft)" }}>
                <span><strong style={{ color: "var(--shpe-navy)" }}>Region:</strong> 5</span>
                <span><strong style={{ color: "var(--shpe-navy)" }}>Chapter Affiliation:</strong> University of Houston Student Chapter</span>
              </div>
            </div>
          </TierCard>
        </div>
      </div>
    </section>
  );
}

export function Points() {
  return (
    <div className="min-h-screen w-full flex flex-col justify-evenly items-center px-6 py-12">
      <h1
        style={{
          backgroundImage: `linear-gradient(rgba(211,58,2,0.95), rgba(211,58,2,0.95)), url(${shpeSpirit})`,
          backgroundBlendMode: 'multiply',
          backgroundSize: 'cover',
          backgroundPosition: 'center center',
          WebkitBackgroundClip: "text",
          backgroundClip: "text",
          color: "transparent",
          WebkitTextFillColor: "transparent",
        }}
        className="text-[clamp(2.25rem,7vw,5rem)] font-bold py-5 text-center"
      >
        The Point System
      </h1>

      <div className="max-w-5xl">
        <p
          className="text-center text-[clamp(1rem,2.2vw,1.8rem)]"
          style={{
            fontFamily: "Work Sans sans-serif"
          }}
        >
          How to earn points...<br />+4 Assist Outreach events <br />+3 General Meeting Sign In<br />+2 General Meeting Sign Out<br />+3 Assist Professional events <br />+2 Assist Off-Campus events <br />+3 Assist SRT/Social events <br />+1 Assist SHPEresenting Thursday<br />+2 Bringing a new member<br />+2 Wearing SHPE shirt for General Meeting<br />+1 Submit Pictures!<br />+2 Assist committee meeting<br />+2 Committee Sign In (Events)<br />+4 Elections/vote<br /><br />The top 5 most active members are awarded at each General meeting!
        </p>
      </div>
    </div>
  )
}

export default function MemberSHPE() {
  useDocumentTitle("MemberSHPE")
  return (
    <>
      <Hero />
      <JoinSecton />
      <Points />
    </>
  );
}