import { SignupRow } from "../SignupFields";
import { columnStyle, fieldStyle } from "../signupStyles";

export default function AccountStep({ form, setField, touch, errorFor }) {
  const field = (name) => ({
    value: form[name],
    onChange: (event) => setField(name, event.target.value),
    onBlur: () => touch(name),
  });
  return (
    <div style={columnStyle}>
      <SignupRow label="First Name" required error={errorFor("first_name")}>
        <input
          style={fieldStyle(errorFor("first_name"))}
          {...field("first_name")}
        />
      </SignupRow>
      <SignupRow label="Last Name" required error={errorFor("last_name")}>
        <input
          style={fieldStyle(errorFor("last_name"))}
          {...field("last_name")}
        />
      </SignupRow>
      <SignupRow
        label="CougarNet Email"
        required
        error={errorFor("cougarnet_email")}
      >
        <input
          style={fieldStyle(errorFor("cougarnet_email"))}
          type="email"
          placeholder="username@cougarnet.uh.edu"
          {...field("cougarnet_email")}
        />
      </SignupRow>
      <SignupRow
        label="Personal Email"
        required
        error={errorFor("personal_email")}
      >
        <input
          style={fieldStyle(errorFor("personal_email"))}
          type="email"
          {...field("personal_email")}
        />
      </SignupRow>
      <SignupRow label="Password" required error={errorFor("password")}>
        <input
          style={fieldStyle(errorFor("password"))}
          type="password"
          placeholder="••••••••"
          {...field("password")}
        />
      </SignupRow>
    </div>
  );
}
