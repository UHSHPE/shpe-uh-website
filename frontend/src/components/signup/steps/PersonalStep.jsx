import { GENDERS } from "../../../constants/userEnums";
import { SignupRow, Toggle } from "../SignupFields";
import { columnStyle, fieldStyle } from "../signupStyles";
import { formatPhone } from "../signupValidation";

export default function PersonalStep({ form, setField, touch, errorFor }) {
  return (
    <div style={columnStyle}>
      <SignupRow label="Gender" required error={errorFor("gender")}>
        <select
          style={fieldStyle(errorFor("gender"))}
          value={form.gender}
          onChange={(event) => setField("gender", event.target.value)}
          onBlur={() => touch("gender")}
        >
          <option value="">Select…</option>
          {GENDERS.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </SignupRow>
      <SignupRow label="First Generation College Student" required>
        <Toggle
          value={form.first_gen}
          onChange={(value) => setField("first_gen", value)}
        />
      </SignupRow>
      <SignupRow label="Birthday" required error={errorFor("birthday")}>
        <input
          style={fieldStyle(errorFor("birthday"))}
          type="date"
          value={form.birthday}
          onChange={(event) => setField("birthday", event.target.value)}
          onBlur={() => touch("birthday")}
        />
      </SignupRow>
      <SignupRow label="PSID" required error={errorFor("psid")}>
        <input
          style={fieldStyle(errorFor("psid"))}
          placeholder="7-digit student ID"
          value={form.psid}
          maxLength={7}
          onChange={(event) => {
            if (/^\d*$/.test(event.target.value))
              setField("psid", event.target.value);
          }}
          onBlur={() => touch("psid")}
        />
      </SignupRow>
      <SignupRow label="Phone Number" required error={errorFor("phone_num")}>
        <input
          style={fieldStyle(errorFor("phone_num"))}
          type="tel"
          inputMode="numeric"
          autoComplete="tel-national"
          placeholder="(555) 555-5555"
          value={form.phone_num}
          onChange={(event) =>
            setField("phone_num", formatPhone(event.target.value))
          }
          onBlur={() => touch("phone_num")}
        />
      </SignupRow>
    </div>
  );
}
