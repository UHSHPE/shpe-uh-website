import { COUNTRIES } from "../../../constants/countries";
import {
  INDUSTRY_OPTIONS,
  PROF_DEV_OPTIONS,
  RACE_ETHNICITY_OPTIONS,
} from "../../../constants/userEnums";
import { MultiCheck, SignupRow } from "../SignupFields";
import { columnStyle, fieldStyle } from "../signupStyles";

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

export default function BackgroundStep({
  form,
  countryInput,
  setCountryInput,
  addCountry,
  removeCountry,
  toggleMulti,
  errorFor,
}) {
  return (
    <div style={columnStyle}>
      <SignupRow label="Race / Ethnicity (select all that apply)" required>
        <MultiCheck
          options={RACE_ETHNICITY_OPTIONS}
          selected={form.race_and_ethnicity}
          onToggle={(value) => toggleMulti("race_and_ethnicity", value)}
        />
      </SignupRow>
      <SignupRow
        label="Country of Origin (select all that apply)"
        required
        error={errorFor("country_origin")}
      >
        <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
          <select
            style={{ ...fieldStyle(errorFor("country_origin")), flex: 1 }}
            value={countryInput}
            onChange={(event) => setCountryInput(event.target.value)}
          >
            <option value="">Select a country…</option>
            {COUNTRIES.filter(
              (item) => !form.country_origin.includes(item),
            ).map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="primaryBtn"
            onClick={addCountry}
            disabled={!countryInput}
            style={{
              padding: "8px 14px",
              fontSize: "13px",
              opacity: countryInput ? 1 : 0.5,
            }}
          >
            Add
          </button>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {form.country_origin.map((country) => (
            <span key={country} style={tagStyle}>
              {country}
              <button
                type="button"
                onClick={() => removeCountry(country)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "#001F5B",
                  fontWeight: 700,
                  marginLeft: "4px",
                  padding: 0,
                }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      </SignupRow>
      <SignupRow label="Interested Industries (select all that apply)" required>
        <MultiCheck
          options={INDUSTRY_OPTIONS}
          selected={form.interested_industries}
          onToggle={(value) => toggleMulti("interested_industries", value)}
        />
      </SignupRow>
      <SignupRow
        label="Professional Development Interests (select all that apply)"
        required
      >
        <MultiCheck
          options={PROF_DEV_OPTIONS}
          selected={form.prof_dev}
          onToggle={(value) => toggleMulti("prof_dev", value)}
        />
      </SignupRow>
    </div>
  );
}
