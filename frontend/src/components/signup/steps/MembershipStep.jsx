import { MEMBERSHIP_STATUSES, SHIRT_SIZES } from "../../../constants/userEnums";
import { SignupRow, Toggle } from "../SignupFields";
import { columnStyle, fieldStyle } from "../signupStyles";

export default function MembershipStep({ form, setField, touch, errorFor }) {
  return (
    <div style={columnStyle}>
      <SignupRow
        label="Membership Status"
        required
        error={errorFor("is_returning")}
      >
        <select
          style={fieldStyle(errorFor("is_returning"))}
          value={form.is_returning}
          onChange={(event) => setField("is_returning", event.target.value)}
          onBlur={() => touch("is_returning")}
        >
          <option value="">Select…</option>
          {MEMBERSHIP_STATUSES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </SignupRow>
      <SignupRow label="National SHPE Member" required>
        <Toggle
          value={form.is_national_member}
          onChange={(value) => setField("is_national_member", value)}
        />
      </SignupRow>
      <SignupRow label="Shirt Size" required error={errorFor("shirt_size")}>
        <select
          style={fieldStyle(errorFor("shirt_size"))}
          value={form.shirt_size}
          onChange={(event) => setField("shirt_size", event.target.value)}
          onBlur={() => touch("shirt_size")}
        >
          <option value="">Select…</option>
          {SHIRT_SIZES.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </SignupRow>
      <SignupRow label="In SHPE Slack" required>
        <Toggle
          value={form.in_slack}
          onChange={(value) => setField("in_slack", value)}
        />
      </SignupRow>
    </div>
  );
}
