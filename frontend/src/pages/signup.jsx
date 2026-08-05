import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { signupUser } from "../api/api";
import { useAuth } from "../context/AuthContext";
import {
  GENDERS, CLASSIFICATIONS, GPA_OPTIONS, EXP_GRAD_DATES,
  MEMBERSHIP_STATUSES, SHIRT_SIZES, COLLEGES, MAJORS_BY_COLLEGE,
  RACE_ETHNICITY_OPTIONS, INDUSTRY_OPTIONS, PROF_DEV_OPTIONS,
} from "../constants/userEnums";
import { COUNTRIES } from "../constants/countries";

const STEPS = ["Account", "Academic", "Personal", "Background", "Membership"];

const emptyForm = {
  first_name: "", last_name: "",
  cougarnet_email: "", personal_email: "", password: "",
  college: "", major: "", classification: "", gpa: "", exp_grad_date: "",
  gender: "", first_gen: false, birthday: "", psid: "", phone_num: "",
  race_and_ethnicity: [], country_origin: [], interested_industries: [], prof_dev: [],
  is_returning: "", is_national_member: false, shirt_size: "", in_slack: false,
};

// Mirrors the backend's _SAFE_NAME_RE (user_schemas.validate_name) — letters,
// hyphens, apostrophes and spaces only. Kept in sync so a name the form
// accepts can't be rejected by the API after five steps of typing.
const NAME_RE = /^[A-Za-zÀ-ÖØ-öø-ÿ' -]{2,50}$/;

// US numbers only, so exactly 10 digits once punctuation is stripped.
function phoneDigits(value) {
  return (value || "").replace(/\D/g, "").slice(0, 10);
}

// Progressive (555) 555-5555 formatting as the member types.
function formatPhone(value) {
  const d = phoneDigits(value);
  if (d.length <= 3) return d;
  if (d.length <= 6) return `(${d.slice(0, 3)}) ${d.slice(3)}`;
  return `(${d.slice(0, 3)}) ${d.slice(3, 6)}-${d.slice(6)}`;
}

function nameError(value, label) {
  const v = (value || "").trim();
  if (!v) return `${label} is required.`;
  if (v.length < 2) return `${label} must be at least 2 characters.`;
  if (!NAME_RE.test(v)) return `${label} can only contain letters, hyphens, and apostrophes.`;
  return "";
}

// Returns an error string for a given field, or "" if valid.
function getFieldError(field, form) {
  switch (field) {
    case "first_name":
      return nameError(form.first_name, "First name");
    case "last_name":
      return nameError(form.last_name, "Last name");
    case "cougarnet_email":
      if (!form.cougarnet_email) return "CougarNet email is required.";
      if (!form.cougarnet_email.toLowerCase().endsWith("@cougarnet.uh.edu"))
        return "Must end with @cougarnet.uh.edu.";
      return "";
    case "personal_email":
      if (!form.personal_email) return "Personal email is required.";
      if (
        form.personal_email.toLowerCase().endsWith("@cougarnet.uh.edu") ||
        form.personal_email.toLowerCase().endsWith("@uh.edu")
      )
        return "Cannot be a CougarNet or UH email.";
      return "";
    case "password":
      if (!form.password) return "Password is required.";
      if (form.password.length < 10) return "Password must be at least 10 characters.";
      return "";
    case "college":
      if (!form.college) return "Please select a college.";
      return "";
    case "major":
      if (!form.major) return "Please select a major.";
      return "";
    case "classification":
      if (!form.classification) return "Please select a classification.";
      return "";
    case "exp_grad_date":
      if (!form.exp_grad_date) return "Please select an expected graduation date.";
      return "";
    case "gender":
      if (!form.gender) return "Please select a gender.";
      return "";
    case "birthday": {
      if (!form.birthday) return "Birthday is required.";
      // Guards the two ways a date input goes wrong: a typo'd year like 0202,
      // and a future date. 13 is the floor because under-13 accounts carry
      // COPPA obligations the chapter isn't set up for.
      const dob = new Date(`${form.birthday}T00:00:00`);
      if (Number.isNaN(dob.getTime())) return "Enter a valid date.";
      const today = new Date();
      if (dob > today) return "Birthday can't be in the future.";
      let age = today.getFullYear() - dob.getFullYear();
      const m = today.getMonth() - dob.getMonth();
      if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) age -= 1;
      if (age < 13) return "You must be at least 13 to sign up.";
      if (age > 120) return "Please check the year.";
      return "";
    }
    case "psid":
      if (!form.psid) return "PSID is required.";
      if (!/^\d{7}$/.test(form.psid)) return "PSID must be exactly 7 digits.";
      return "";
    case "phone_num": {
      if (!form.phone_num.trim()) return "Phone number is required.";
      const digits = phoneDigits(form.phone_num);
      if (digits.length !== 10) return "Enter a 10-digit US phone number.";
      if (digits[0] === "0" || digits[0] === "1") return "Area code can't start with 0 or 1.";
      return "";
    }
    case "country_origin":
      if (form.country_origin.length === 0) return "Please add at least one country.";
      return "";
    case "is_returning":
      if (!form.is_returning) return "Please select your membership status.";
      return "";
    case "shirt_size":
      if (!form.shirt_size) return "Please select a shirt size.";
      return "";
    default:
      return "";
  }
}

export default function SignUp() {
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(emptyForm);
  const [touched, setTouched] = useState({});
  const [countryInput, setCountryInput] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [loading, setLoading] = useState(false);
  // Set once signup succeeds — the account exists but is unverified, so we
  // show a "check your email" screen instead of logging in. Dues checkout now
  // happens on the verify-email page (the buyer must be signed in to pay).
  const [submittedEmail, setSubmittedEmail] = useState("");

  if (user) {
    return <Navigate to="/dashboard" replace />
  }

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  // `touched` is keyed by STEP, not just by field: { 2: { psid: true } }.
  //
  // A flat map meant every transition had to remember to clear it, and any
  // path that didn't — a stray onBlur, browser autofill, a handler added
  // later — left a fresh step opening covered in "required" errors before the
  // member typed anything. Keying by step makes that impossible by
  // construction: a step the member hasn't interacted with has no entry, so
  // there is nothing to leak and nothing to reset.
  function touch(field) {
    setTouched((prev) => ({ ...prev, [step]: { ...prev[step], [field]: true } }));
  }

  // Returns the error only if the field has been touched on this step.
  function err(field) {
    return touched[step]?.[field] ? getFieldError(field, form) : "";
  }

  function toggleMulti(field, value) {
    setForm((prev) => {
      const list = prev[field];
      return {
        ...prev,
        [field]: list.includes(value) ? list.filter((v) => v !== value) : [...list, value],
      };
    });
  }

  function addCountry() {
    const trimmed = countryInput.trim();
    if (!trimmed || form.country_origin.includes(trimmed)) return;
    set("country_origin", [...form.country_origin, trimmed]);
    setCountryInput("");
    touch("country_origin");
  }

  function removeCountry(c) {
    set("country_origin", form.country_origin.filter((v) => v !== c));
  }

  const FIELDS_BY_STEP = [
    ["first_name", "last_name", "cougarnet_email", "personal_email", "password"],
    ["college", "major", "classification", "exp_grad_date"],
    ["gender", "birthday", "psid", "phone_num"],
    ["country_origin"],
    ["is_returning", "shirt_size"],
  ];

  // Touch every field on a step so its errors become visible — on Next for the
  // current step, or on the final submit for whichever step is incomplete.
  function touchAllOnStep(s) {
    const fields = FIELDS_BY_STEP[s] || [];
    setTouched((prev) => ({
      ...prev,
      [s]: { ...prev[s], ...Object.fromEntries(fields.map((f) => [f, true])) },
    }));
    return fields;
  }

  // Rules for one step, by index. Takes the index explicitly (rather than
  // reading `step`) so the final submit can re-check every earlier step.
  function validateStepAt(s) {
    if (s === 0 || s === 2) {
      for (const f of FIELDS_BY_STEP[s]) {
        const e = getFieldError(f, form);
        if (e) return e;
      }
    }
    if (s === 1) {
      if (!form.college || !form.major || !form.classification || !form.exp_grad_date)
        return "Please fill in all required fields.";
    }
    if (s === 3) {
      if (form.race_and_ethnicity.length === 0) return "Please select at least one race/ethnicity option.";
      if (form.country_origin.length === 0) return "Please add at least one country of origin.";
      if (form.interested_industries.length === 0) return "Please select at least one interested industry.";
      if (form.prof_dev.length === 0) return "Please select at least one professional development interest.";
    }
    if (s === 4) {
      if (!form.is_returning || !form.shirt_size) return "Please fill in all required fields.";
    }
    return "";
  }

  function validateStep() {
    return validateStepAt(step);
  }

  // The earliest step that still fails, or -1. Without this, a field skipped
  // earlier only surfaces as a 422 from the API after "Create Account".
  function firstIncompleteStep() {
    for (let s = 0; s < STEPS.length; s += 1) {
      if (validateStepAt(s)) return s;
    }
    return -1;
  }

  // `touched` is keyed by step, so a step change needs no reset — only the
  // banner, which is about the step you were on.
  function goToStep(next) {
    setSubmitError("");
    setStep(next);
  }

  function nextStep() {
    touchAllOnStep(step);
    const error = validateStep();
    if (error) { setSubmitError(error); return; }
    goToStep(step + 1);
  }

  async function handleSubmit(e) {
    e.preventDefault();

    // The whole wizard lives in one <form>, so pressing Enter in any text
    // field fires submit — on an earlier step that used to POST a half-filled
    // payload and surface the API's validation errors out of nowhere. Treat
    // Enter as "Next" until the member is actually on the last step.
    if (step < STEPS.length - 1) { nextStep(); return; }

    touchAllOnStep(step);
    const error = validateStep();
    if (error) { setSubmitError(error); return; }

    // Everything before this step has to hold too, or the API rejects it.
    const incomplete = firstIncompleteStep();
    if (incomplete !== -1) {
      setSubmitError(`Please finish the "${STEPS[incomplete]}" step — ${validateStepAt(incomplete)}`);
      touchAllOnStep(incomplete);
      setStep(incomplete);
      return;
    }
    setSubmitError("");
    setLoading(true);

    const payload = { ...form, gpa: form.gpa || null };

    try {
      await signupUser(payload);
      // Account created but unverified — no token comes back. Prompt the
      // member to confirm via the link we just emailed to their CougarNet
      // address; verification is where they'll be routed into dues checkout.
      setSubmittedEmail(form.cougarnet_email);
    } catch (err) {
      if (err.response?.data?.detail) {
        // Covers both the email-conflict and PSID-conflict 409s (and any
        // other detail-bearing error) — surface the server's message
        // verbatim rather than guessing which field it was about.
        const detail = err.response.data.detail;
        setSubmitError(Array.isArray(detail) ? detail.map((d) => d.msg).join(" ") : String(detail));
      } else {
        setSubmitError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  const majorOptions = form.college ? (MAJORS_BY_COLLEGE[form.college] || []) : [];

  if (submittedEmail) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #001F5B 0%, #003A70 60%, #0070C0 100%)",
          padding: "24px 16px",
          fontFamily: "Work Sans, sans-serif",
        }}
      >
        <div
          style={{
            background: "#fff",
            borderRadius: "16px",
            padding: "48px 40px",
            width: "100%",
            maxWidth: "460px",
            boxShadow: "0 20px 60px rgba(0,0,0,0.25)",
            textAlign: "center",
          }}
        >
          <h1 style={{ fontSize: "26px", fontWeight: 700, color: "#001F5B", marginBottom: "12px" }}>
            Check your email
          </h1>
          <p style={{ color: "#374151", fontSize: "15px", lineHeight: 1.6 }}>
            We sent a verification link to{" "}
            <strong style={{ color: "#001F5B" }}>{submittedEmail}</strong>. Click it to
            activate your account and pay your chapter dues.
          </p>
          <p style={{ color: "#6b7280", fontSize: "14px", marginTop: "16px", lineHeight: 1.6 }}>
            The link expires in 24 hours. Didn't get it? Check your spam folder, or
            sign up again to resend.
          </p>
          <p style={{ marginTop: "28px", fontSize: "14px" }}>
            <Link to="/signin" style={{ color: "#0070C0", fontWeight: 600, textDecoration: "none" }}>
              Back to sign in
            </Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #001F5B 0%, #003A70 60%, #0070C0 100%)",
        padding: "24px 16px",
        fontFamily: "Work Sans, sans-serif",
      }}
    >
      <div
        style={{
          background: "#fff",
          borderRadius: "16px",
          padding: "40px",
          width: "100%",
          maxWidth: "520px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.25)",
        }}
      >
        {/* Progress */}
        <div style={{ marginBottom: "28px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
            {STEPS.map((label, i) => (
              <span
                key={label}
                style={{
                  fontSize: "11px",
                  fontWeight: i <= step ? 700 : 400,
                  color: i < step ? "#0070C0" : i === step ? "#001F5B" : "#9ca3af",
                }}
              >
                {label}
              </span>
            ))}
          </div>
          <div style={{ height: "4px", background: "#e5e7eb", borderRadius: "99px", overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${((step + 1) / STEPS.length) * 100}%`,
                background: "linear-gradient(90deg, #001F5B, #0070C0)",
                borderRadius: "99px",
                transition: "width 0.3s ease",
              }}
            />
          </div>
        </div>

        <h1 style={{ fontSize: "22px", fontWeight: 700, color: "#001F5B", marginBottom: "4px" }}>
          {STEPS[step]}
        </h1>
        <p style={{ color: "#6b7280", fontSize: "14px", marginBottom: "24px" }}>
          Step {step + 1} of {STEPS.length}
        </p>

        <form onSubmit={handleSubmit}>
          {step === 0 && (
            <div style={colStyle}>
              <Row label="First Name" required error={err("first_name")}>
                <input
                  style={fieldStyle(err("first_name"))}
                  value={form.first_name}
                  onChange={(e) => set("first_name", e.target.value)}
                  onBlur={() => touch("first_name")}
                />
              </Row>
              <Row label="Last Name" required error={err("last_name")}>
                <input
                  style={fieldStyle(err("last_name"))}
                  value={form.last_name}
                  onChange={(e) => set("last_name", e.target.value)}
                  onBlur={() => touch("last_name")}
                />
              </Row>
              <Row label="CougarNet Email" required error={err("cougarnet_email")}>
                <input
                  style={fieldStyle(err("cougarnet_email"))}
                  type="email"
                  placeholder="username@cougarnet.uh.edu"
                  value={form.cougarnet_email}
                  onChange={(e) => set("cougarnet_email", e.target.value)}
                  onBlur={() => touch("cougarnet_email")}
                />
              </Row>
              <Row label="Personal Email" required error={err("personal_email")}>
                <input
                  style={fieldStyle(err("personal_email"))}
                  type="email"
                  value={form.personal_email}
                  onChange={(e) => set("personal_email", e.target.value)}
                  onBlur={() => touch("personal_email")}
                />
              </Row>
              <Row label="Password" required error={err("password")}>
                <input
                  style={fieldStyle(err("password"))}
                  type="password"
                  placeholder="••••••••"
                  value={form.password}
                  onChange={(e) => set("password", e.target.value)}
                  onBlur={() => touch("password")}
                />
              </Row>
            </div>
          )}

          {step === 1 && (
            <div style={colStyle}>
              <Row label="College" required error={err("college")}>
                <select
                  style={fieldStyle(err("college"))}
                  value={form.college}
                  onChange={(e) => { set("college", e.target.value); set("major", ""); }}
                  onBlur={() => touch("college")}
                >
                  <option value="">Select college…</option>
                  {COLLEGES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </Row>
              <Row label="Major" required error={err("major")}>
                {form.college === "Other" ? (
                  <input
                    style={fieldStyle(err("major"))}
                    placeholder="Enter your major"
                    value={form.major}
                    onChange={(e) => set("major", e.target.value)}
                    onBlur={() => touch("major")}
                  />
                ) : (
                  <select
                    style={fieldStyle(err("major"))}
                    value={form.major}
                    onChange={(e) => set("major", e.target.value)}
                    onBlur={() => touch("major")}
                    disabled={!form.college}
                  >
                    <option value="">Select major…</option>
                    {majorOptions.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                )}
              </Row>
              <Row label="Classification" required error={err("classification")}>
                <select
                  style={fieldStyle(err("classification"))}
                  value={form.classification}
                  onChange={(e) => set("classification", e.target.value)}
                  onBlur={() => touch("classification")}
                >
                  <option value="">Select…</option>
                  {CLASSIFICATIONS.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </Row>
              <Row label="GPA">
                <select style={inputStyle} value={form.gpa} onChange={(e) => set("gpa", e.target.value)}>
                  <option value="">Select (optional)…</option>
                  {GPA_OPTIONS.map((g) => <option key={g} value={g}>{g}</option>)}
                </select>
              </Row>
              <Row label="Expected Graduation" required error={err("exp_grad_date")}>
                <select
                  style={fieldStyle(err("exp_grad_date"))}
                  value={form.exp_grad_date}
                  onChange={(e) => set("exp_grad_date", e.target.value)}
                  onBlur={() => touch("exp_grad_date")}
                >
                  <option value="">Select…</option>
                  {EXP_GRAD_DATES.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
              </Row>
            </div>
          )}

          {step === 2 && (
            <div style={colStyle}>
              <Row label="Gender" required error={err("gender")}>
                <select
                  style={fieldStyle(err("gender"))}
                  value={form.gender}
                  onChange={(e) => set("gender", e.target.value)}
                  onBlur={() => touch("gender")}
                >
                  <option value="">Select…</option>
                  {GENDERS.map((g) => <option key={g} value={g}>{g}</option>)}
                </select>
              </Row>
              <Row label="First Generation College Student" required>
                <Toggle value={form.first_gen} onChange={(v) => set("first_gen", v)} />
              </Row>
              <Row label="Birthday" required error={err("birthday")}>
                <input
                  style={fieldStyle(err("birthday"))}
                  type="date"
                  value={form.birthday}
                  onChange={(e) => set("birthday", e.target.value)}
                  onBlur={() => touch("birthday")}
                />
              </Row>
              <Row label="PSID" required error={err("psid")}>
                <input
                  style={fieldStyle(err("psid"))}
                  placeholder="7-digit student ID"
                  value={form.psid}
                  maxLength={7}
                  onChange={(e) => { if (/^\d*$/.test(e.target.value)) set("psid", e.target.value); }}
                  onBlur={() => touch("psid")}
                />
              </Row>
              <Row label="Phone Number" required error={err("phone_num")}>
                <input
                  style={fieldStyle(err("phone_num"))}
                  type="tel"
                  inputMode="numeric"
                  autoComplete="tel-national"
                  placeholder="(555) 555-5555"
                  value={form.phone_num}
                  // Formats as they type and hard-stops at 10 digits, so a US
                  // number can't be over-typed and the backend can't see one.
                  onChange={(e) => set("phone_num", formatPhone(e.target.value))}
                  onBlur={() => touch("phone_num")}
                />
              </Row>
            </div>
          )}

          {step === 3 && (
            <div style={colStyle}>
              <Row label="Race / Ethnicity (select all that apply)" required>
                <MultiCheck options={RACE_ETHNICITY_OPTIONS} selected={form.race_and_ethnicity} onToggle={(v) => toggleMulti("race_and_ethnicity", v)} />
              </Row>
              <Row label="Country of Origin (select all that apply)" required error={err("country_origin")}>
                <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
                  <select
                    style={{ ...fieldStyle(err("country_origin")), flex: 1 }}
                    value={countryInput}
                    onChange={(e) => setCountryInput(e.target.value)}
                  >
                    <option value="">Select a country…</option>
                    {COUNTRIES.filter((c) => !form.country_origin.includes(c)).map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="primaryBtn"
                    onClick={addCountry}
                    disabled={!countryInput}
                    style={{ padding: "8px 14px", fontSize: "13px", opacity: countryInput ? 1 : 0.5 }}
                  >
                    Add
                  </button>
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {form.country_origin.map((c) => (
                    <span key={c} style={tagStyle}>
                      {c}
                      <button type="button" onClick={() => removeCountry(c)} style={{ background: "none", border: "none", cursor: "pointer", color: "#001F5B", fontWeight: 700, marginLeft: "4px", padding: 0 }}>×</button>
                    </span>
                  ))}
                </div>
              </Row>
              <Row label="Interested Industries (select all that apply)" required>
                <MultiCheck options={INDUSTRY_OPTIONS} selected={form.interested_industries} onToggle={(v) => toggleMulti("interested_industries", v)} />
              </Row>
              <Row label="Professional Development Interests (select all that apply)" required>
                <MultiCheck options={PROF_DEV_OPTIONS} selected={form.prof_dev} onToggle={(v) => toggleMulti("prof_dev", v)} />
              </Row>
            </div>
          )}

          {step === 4 && (
            <div style={colStyle}>
              <Row label="Membership Status" required error={err("is_returning")}>
                <select
                  style={fieldStyle(err("is_returning"))}
                  value={form.is_returning}
                  onChange={(e) => set("is_returning", e.target.value)}
                  onBlur={() => touch("is_returning")}
                >
                  <option value="">Select…</option>
                  {MEMBERSHIP_STATUSES.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </Row>
              <Row label="National SHPE Member" required>
                <Toggle value={form.is_national_member} onChange={(v) => set("is_national_member", v)} />
              </Row>
              <Row label="Shirt Size" required error={err("shirt_size")}>
                <select
                  style={fieldStyle(err("shirt_size"))}
                  value={form.shirt_size}
                  onChange={(e) => set("shirt_size", e.target.value)}
                  onBlur={() => touch("shirt_size")}
                >
                  <option value="">Select…</option>
                  {SHIRT_SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </Row>
              <Row label="In SHPE Slack" required>
                <Toggle value={form.in_slack} onChange={(v) => set("in_slack", v)} />
              </Row>
            </div>
          )}

          {submitError && (
            <p style={{ color: "#D33A02", fontSize: "14px", fontWeight: 500, margin: "12px 0 0" }}>
              {submitError}
            </p>
          )}

          <div style={{ display: "flex", gap: "12px", marginTop: "28px" }}>
            {step > 0 && (
              <button type="button" className="ghostBtn" onClick={() => goToStep(step - 1)} style={{ flex: 1, padding: "12px" }}>
                Back
              </button>
            )}
            {step < STEPS.length - 1 ? (
              <button type="button" className="primaryBtn" onClick={nextStep} style={{ flex: 1, padding: "12px" }}>
                Next
              </button>
            ) : (
              <button type="submit" className="primaryBtn" disabled={loading} style={{ flex: 1, padding: "12px", opacity: loading ? 0.7 : 1 }}>
                {loading ? "Creating account…" : "Create Account"}
              </button>
            )}
          </div>
        </form>

        <p style={{ textAlign: "center", marginTop: "20px", fontSize: "14px", color: "#6b7280" }}>
          Already have an account?{" "}
          <Link to="/signin" style={{ color: "#0070C0", fontWeight: 600, textDecoration: "none" }}>
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

function Row({ label, required, error, children }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
      <label style={{ fontSize: "13px", fontWeight: 600, color: "#374151" }}>
        {label}{required && <span style={{ color: "#D33A02" }}> *</span>}
      </label>
      {children}
      {error && (
        <p style={{ margin: 0, fontSize: "12px", color: "#D33A02", fontWeight: 500 }}>{error}</p>
      )}
    </div>
  );
}

function Toggle({ value, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      style={{
        width: "48px", height: "26px", borderRadius: "99px",
        background: value ? "#0070C0" : "#d1d5db",
        border: "none", cursor: "pointer", position: "relative", transition: "background 0.2s",
      }}
    >
      <span style={{
        position: "absolute", top: "3px",
        left: value ? "24px" : "3px",
        width: "20px", height: "20px",
        borderRadius: "50%", background: "#fff",
        transition: "left 0.2s", boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
      }} />
    </button>
  );
}

function MultiCheck({ options, selected, onToggle }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "180px", overflowY: "auto", padding: "4px 0" }}>
      {options.map((opt) => (
        <label key={opt} style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={selected.includes(opt)}
            onChange={() => onToggle(opt)}
            style={{ accentColor: "#0070C0", width: "15px", height: "15px" }}
          />
          {opt}
        </label>
      ))}
    </div>
  );
}

const colStyle = { display: "flex", flexDirection: "column", gap: "16px" };

const inputStyle = {
  padding: "10px 14px",
  borderRadius: "8px",
  border: "1.5px solid #d1d5db",
  fontSize: "14px",
  outline: "none",
  fontFamily: "Work Sans, sans-serif",
  width: "100%",
  boxSizing: "border-box",
};

function fieldStyle(error) {
  return {
    ...inputStyle,
    border: `1.5px solid ${error ? "#D33A02" : "#d1d5db"}`,
  };
}

const tagStyle = {
  background: "#e0f0ff",
  color: "#001F5B",
  borderRadius: "99px",
  padding: "3px 10px",
  fontSize: "12px",
  fontWeight: 600,
  display: "flex",
  alignItems: "center",
};
