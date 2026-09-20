import {
  CLASSIFICATIONS,
  COLLEGES,
  EXP_GRAD_DATES,
  GPA_OPTIONS,
  MAJORS_BY_COLLEGE,
} from "../../../constants/userEnums";
import { SignupRow } from "../SignupFields";
import { columnStyle, fieldStyle, inputStyle } from "../signupStyles";

export default function AcademicStep({ form, setField, touch, errorFor }) {
  const majorOptions = form.college
    ? MAJORS_BY_COLLEGE[form.college] || []
    : [];
  return (
    <div style={columnStyle}>
      <SignupRow label="College" required error={errorFor("college")}>
        <select
          style={fieldStyle(errorFor("college"))}
          value={form.college}
          onChange={(event) => {
            setField("college", event.target.value);
            setField("major", "");
          }}
          onBlur={() => touch("college")}
        >
          <option value="">Select college…</option>
          {COLLEGES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </SignupRow>
      <SignupRow label="Major" required error={errorFor("major")}>
        {form.college === "Other" ? (
          <input
            style={fieldStyle(errorFor("major"))}
            placeholder="Enter your major"
            value={form.major}
            onChange={(event) => setField("major", event.target.value)}
            onBlur={() => touch("major")}
          />
        ) : (
          <select
            style={fieldStyle(errorFor("major"))}
            value={form.major}
            onChange={(event) => setField("major", event.target.value)}
            onBlur={() => touch("major")}
            disabled={!form.college}
          >
            <option value="">Select major…</option>
            {majorOptions.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        )}
      </SignupRow>
      <SignupRow
        label="Classification"
        required
        error={errorFor("classification")}
      >
        <select
          style={fieldStyle(errorFor("classification"))}
          value={form.classification}
          onChange={(event) => setField("classification", event.target.value)}
          onBlur={() => touch("classification")}
        >
          <option value="">Select…</option>
          {CLASSIFICATIONS.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </SignupRow>
      <SignupRow label="GPA">
        <select
          style={inputStyle}
          value={form.gpa}
          onChange={(event) => setField("gpa", event.target.value)}
        >
          <option value="">Select (optional)…</option>
          {GPA_OPTIONS.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </SignupRow>
      <SignupRow
        label="Expected Graduation"
        required
        error={errorFor("exp_grad_date")}
      >
        <select
          style={fieldStyle(errorFor("exp_grad_date"))}
          value={form.exp_grad_date}
          onChange={(event) => setField("exp_grad_date", event.target.value)}
          onBlur={() => touch("exp_grad_date")}
        >
          <option value="">Select…</option>
          {EXP_GRAD_DATES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </SignupRow>
    </div>
  );
}
