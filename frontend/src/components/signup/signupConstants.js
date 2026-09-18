export const SIGNUP_STEPS = [
  "Account",
  "Academic",
  "Personal",
  "Background",
  "Membership",
];

export const EMPTY_SIGNUP_FORM = {
  first_name: "",
  last_name: "",
  cougarnet_email: "",
  personal_email: "",
  password: "",
  college: "",
  major: "",
  classification: "",
  gpa: "",
  exp_grad_date: "",
  gender: "",
  first_gen: false,
  birthday: "",
  psid: "",
  phone_num: "",
  race_and_ethnicity: [],
  country_origin: [],
  interested_industries: [],
  prof_dev: [],
  is_returning: "",
  is_national_member: false,
  shirt_size: "",
  in_slack: false,
};

export const FIELDS_BY_STEP = [
  ["first_name", "last_name", "cougarnet_email", "personal_email", "password"],
  ["college", "major", "classification", "exp_grad_date"],
  ["gender", "birthday", "psid", "phone_num"],
  ["country_origin"],
  ["is_returning", "shirt_size"],
];
