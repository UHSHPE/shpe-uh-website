import { FIELDS_BY_STEP } from "./signupConstants";

const NAME_RE = /^[A-Za-zÀ-ÖØ-öø-ÿ' -]{2,50}$/;

export function phoneDigits(value) {
  return (value || "").replace(/\D/g, "").slice(0, 10);
}

export function formatPhone(value) {
  const digits = phoneDigits(value);
  if (digits.length <= 3) return digits;
  if (digits.length <= 6) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
  return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
}

function nameError(value, label) {
  const trimmed = (value || "").trim();
  if (!trimmed) return `${label} is required.`;
  if (trimmed.length < 2) return `${label} must be at least 2 characters.`;
  if (!NAME_RE.test(trimmed))
    return `${label} can only contain letters, hyphens, and apostrophes.`;
  return "";
}

export function getFieldError(field, form) {
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
      if (form.password.length < 10)
        return "Password must be at least 10 characters.";
      return "";
    case "college":
      return form.college ? "" : "Please select a college.";
    case "major":
      return form.major ? "" : "Please select a major.";
    case "classification":
      return form.classification ? "" : "Please select a classification.";
    case "exp_grad_date":
      return form.exp_grad_date
        ? ""
        : "Please select an expected graduation date.";
    case "gender":
      return form.gender ? "" : "Please select a gender.";
    case "birthday": {
      if (!form.birthday) return "Birthday is required.";
      const birthday = new Date(`${form.birthday}T00:00:00`);
      if (Number.isNaN(birthday.getTime())) return "Enter a valid date.";
      const today = new Date();
      if (birthday > today) return "Birthday can't be in the future.";
      let age = today.getFullYear() - birthday.getFullYear();
      const monthDifference = today.getMonth() - birthday.getMonth();
      if (
        monthDifference < 0 ||
        (monthDifference === 0 && today.getDate() < birthday.getDate())
      )
        age -= 1;
      if (age < 13) return "You must be at least 13 to sign up.";
      if (age > 120) return "Please check the year.";
      return "";
    }
    case "psid":
      if (!form.psid) return "PSID is required.";
      return /^\d{7}$/.test(form.psid) ? "" : "PSID must be exactly 7 digits.";
    case "phone_num": {
      if (!form.phone_num.trim()) return "Phone number is required.";
      const digits = phoneDigits(form.phone_num);
      if (digits.length !== 10) return "Enter a 10-digit US phone number.";
      if (digits[0] === "0" || digits[0] === "1")
        return "Area code can't start with 0 or 1.";
      return "";
    }
    case "country_origin":
      return form.country_origin.length
        ? ""
        : "Please add at least one country.";
    case "is_returning":
      return form.is_returning ? "" : "Please select your membership status.";
    case "shirt_size":
      return form.shirt_size ? "" : "Please select a shirt size.";
    default:
      return "";
  }
}

export function validateSignupStep(step, form) {
  if (step === 0 || step === 2) {
    for (const field of FIELDS_BY_STEP[step]) {
      const error = getFieldError(field, form);
      if (error) return error;
    }
  }
  if (
    step === 1 &&
    (!form.college ||
      !form.major ||
      !form.classification ||
      !form.exp_grad_date)
  )
    return "Please fill in all required fields.";
  if (step === 3) {
    if (form.race_and_ethnicity.length === 0)
      return "Please select at least one race/ethnicity option.";
    if (form.country_origin.length === 0)
      return "Please add at least one country of origin.";
    if (form.interested_industries.length === 0)
      return "Please select at least one interested industry.";
    if (form.prof_dev.length === 0)
      return "Please select at least one professional development interest.";
  }
  if (step === 4 && (!form.is_returning || !form.shirt_size))
    return "Please fill in all required fields.";
  return "";
}
