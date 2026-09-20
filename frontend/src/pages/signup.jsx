import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { signupUser } from "../api/api";
import SignupProgress from "../components/signup/SignupProgress";
import SignupSuccess from "../components/signup/SignupSuccess";
import {
  EMPTY_SIGNUP_FORM,
  FIELDS_BY_STEP,
  SIGNUP_STEPS,
} from "../components/signup/signupConstants";
import {
  getFieldError,
  validateSignupStep,
} from "../components/signup/signupValidation";
import AcademicStep from "../components/signup/steps/AcademicStep";
import AccountStep from "../components/signup/steps/AccountStep";
import BackgroundStep from "../components/signup/steps/BackgroundStep";
import MembershipStep from "../components/signup/steps/MembershipStep";
import PersonalStep from "../components/signup/steps/PersonalStep";
import { useAuth } from "../context/AuthContext";
import useDocumentTitle from "../hooks/useDocumentTitle";

export default function SignUp() {
  useDocumentTitle("Sign Up");
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState(EMPTY_SIGNUP_FORM);
  const [touched, setTouched] = useState({});
  const [countryInput, setCountryInput] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [loading, setLoading] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState("");

  if (user) return <Navigate to="/dashboard" replace />;

  function setField(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }));
  }

  // Touched fields are grouped by step so errors cannot leak into an
  // untouched step when browser autofill or navigation changes state.
  function touch(field) {
    setTouched((previous) => ({
      ...previous,
      [step]: { ...previous[step], [field]: true },
    }));
  }

  function errorFor(field) {
    return touched[step]?.[field] ? getFieldError(field, form) : "";
  }

  function toggleMulti(field, value) {
    setForm((previous) => ({
      ...previous,
      [field]: previous[field].includes(value)
        ? previous[field].filter((item) => item !== value)
        : [...previous[field], value],
    }));
  }

  function addCountry() {
    const country = countryInput.trim();
    if (!country || form.country_origin.includes(country)) return;
    setField("country_origin", [...form.country_origin, country]);
    setCountryInput("");
    touch("country_origin");
  }

  function removeCountry(country) {
    setField(
      "country_origin",
      form.country_origin.filter((item) => item !== country),
    );
  }

  function touchAllOnStep(stepIndex) {
    const fields = FIELDS_BY_STEP[stepIndex] || [];
    setTouched((previous) => ({
      ...previous,
      [stepIndex]: {
        ...previous[stepIndex],
        ...Object.fromEntries(fields.map((field) => [field, true])),
      },
    }));
  }

  function firstIncompleteStep() {
    for (let stepIndex = 0; stepIndex < SIGNUP_STEPS.length; stepIndex += 1) {
      if (validateSignupStep(stepIndex, form)) return stepIndex;
    }
    return -1;
  }

  function goToStep(nextStep) {
    setSubmitError("");
    setStep(nextStep);
  }

  function nextStep() {
    touchAllOnStep(step);
    const error = validateSignupStep(step, form);
    if (error) {
      setSubmitError(error);
      return;
    }

    // A forward transition represents the first untouched view of the next
    // step. Clear any stale entry before rendering it so required-field
    // errors cannot appear until the member interacts with that step.
    const nextStepIndex = step + 1;
    setTouched((previous) => {
      const next = { ...previous };
      delete next[nextStepIndex];
      return next;
    });
    goToStep(nextStepIndex);
  }

  async function handleSubmit(event) {
    event.preventDefault();

    // Enter behaves like Next until the member reaches the final step.
    if (step < SIGNUP_STEPS.length - 1) {
      nextStep();
      return;
    }

    touchAllOnStep(step);
    const error = validateSignupStep(step, form);
    if (error) {
      setSubmitError(error);
      return;
    }

    const incompleteStep = firstIncompleteStep();
    if (incompleteStep !== -1) {
      setSubmitError(
        `Please finish the "${SIGNUP_STEPS[incompleteStep]}" step — ${validateSignupStep(incompleteStep, form)}`,
      );
      touchAllOnStep(incompleteStep);
      setStep(incompleteStep);
      return;
    }

    setSubmitError("");
    setLoading(true);
    try {
      await signupUser({ ...form, gpa: form.gpa || null });
      setSubmittedEmail(form.cougarnet_email);
    } catch (requestError) {
      const detail = requestError.response?.data?.detail;
      if (detail) {
        setSubmitError(
          Array.isArray(detail)
            ? detail.map((item) => item.msg).join(" ")
            : String(detail),
        );
      } else {
        setSubmitError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  if (submittedEmail) return <SignupSuccess email={submittedEmail} />;

  const stepProps = { form, setField, touch, errorFor };

  return (
    <div
      style={{
        minHeight: "calc(100vh - var(--header-height))",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background:
          "linear-gradient(135deg, #001F5B 0%, #003A70 60%, #0070C0 100%)",
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
        <SignupProgress step={step} />
        <h1
          style={{
            fontSize: "22px",
            fontWeight: 700,
            color: "#001F5B",
            marginBottom: "4px",
          }}
        >
          {SIGNUP_STEPS[step]}
        </h1>
        <p style={{ color: "#6b7280", fontSize: "14px", marginBottom: "24px" }}>
          Step {step + 1} of {SIGNUP_STEPS.length}
        </p>

        <form onSubmit={handleSubmit}>
          {step === 0 && <AccountStep {...stepProps} />}
          {step === 1 && <AcademicStep {...stepProps} />}
          {step === 2 && <PersonalStep {...stepProps} />}
          {step === 3 && (
            <BackgroundStep
              form={form}
              countryInput={countryInput}
              setCountryInput={setCountryInput}
              addCountry={addCountry}
              removeCountry={removeCountry}
              toggleMulti={toggleMulti}
              errorFor={errorFor}
            />
          )}
          {step === 4 && <MembershipStep {...stepProps} />}

          {submitError && (
            <p
              style={{
                color: "#D33A02",
                fontSize: "14px",
                fontWeight: 500,
                margin: "12px 0 0",
              }}
            >
              {submitError}
            </p>
          )}
          <div style={{ display: "flex", gap: "12px", marginTop: "28px" }}>
            {step > 0 && (
              <button
                type="button"
                className="ghostBtn"
                onClick={() => goToStep(step - 1)}
                style={{ flex: 1, padding: "12px" }}
              >
                Back
              </button>
            )}
            {step < SIGNUP_STEPS.length - 1 ? (
              <button
                key="next-step"
                type="button"
                className="primaryBtn"
                onClick={(event) => {
                  // React replaces this control with the final submit button
                  // after the Background step. Prevent the current click's
                  // browser default before that replacement can occur.
                  event.preventDefault();
                  nextStep();
                }}
                style={{ flex: 1, padding: "12px" }}
              >
                Next
              </button>
            ) : (
              <button
                key="create-account"
                type="submit"
                className="primaryBtn"
                disabled={loading}
                style={{ flex: 1, padding: "12px", opacity: loading ? 0.7 : 1 }}
              >
                {loading ? "Creating account…" : "Create Account"}
              </button>
            )}
          </div>
        </form>

        <p
          style={{
            textAlign: "center",
            marginTop: "20px",
            fontSize: "14px",
            color: "#6b7280",
          }}
        >
          Already have an account?{" "}
          <Link
            to="/signin"
            style={{
              color: "#0070C0",
              fontWeight: 600,
              textDecoration: "none",
            }}
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
