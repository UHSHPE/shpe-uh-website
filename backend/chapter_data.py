"""Real chapter structure: committees, the org chart, and the dues product.

This is the data BOTH seeders need, split out so production can have it
without the fake accounts. seed.py (local dev) adds ~30 users all sharing
password123 and refuses to run under ENVIRONMENT=production; bootstrap.py
creates only the rows below and is safe to run against the live database.

bootstrap.py cannot simply import these from seed.py — seed's module-level
sys.exit(1) fires on import in production. Copying them instead would mean a
15th committee has to be added in two files, which drifts silently (the exact
failure this repo already documents for the About page roster). So the data
lives here and both scripts import it.

Data only — no logic, no side effects.
"""
from models.shop.product import ProductType
from models.user.user_enums import Role
from services.shop_services import DUES_PRODUCT_NAME

# Official committee roster. Each committee has exactly one chair role;
# co-chairs share that role and each get a CommitteeMembership with is_chair=True.
# Format: (committee name, description, chair role, [chair full names])
#
# The chair NAMES are dev-seed data only — bootstrap.py ignores that fourth
# element, because in production chairs are real people who sign up and are
# then promoted through /members.
COMMITTEE_ROSTER = [
    ("Academic", "Study sessions, tutoring, and academic support for members.", Role.academic_chair, ["Angel Montoya", "Sophia Rodriguez"]),
    ("Athletics and Wellness", "Intramural sports, fitness events, and wellness activities.", Role.athletic_chair, ["Smiley Trenton", "Ean Plasencia"]),
    ("CFC", "Plans and runs the SHPE UH career fair and recruiter relations.", Role.career_fair_chair, ["Sara Romero"]),
    ("Engineering Events Coordinator", "Coordinates engineering competitions and technical events.", Role.eec_chair, ["David Cohen", "Ethan Lopez"]),
    ("Marketing", "Social media, branding, and chapter promotion.", Role.marketing_chair, ["Valeria Zabala"]),
    ("MentorSHPE", "Peer mentorship program pairing upperclassmen with freshmen.", Role.mentorshpe_chair, ["Nicolas Horton", "Mia Flores"]),
    ("Outreach", "STEM outreach programs to K-12 schools in the Houston area.", Role.outreach_chair, ["Khris Flores"]),
    ("Professional", "Resume workshops, networking events, and professional development.", Role.professional_chair, ["Rhonmar Joseph Marges"]),
    ("Projects", "Hands-on technical projects and competition teams.", Role.projects_chair, ["Lorenzo Ramos", "Alfonso Salas"]),
    ("SHPE Jr", "Mentors local high school SHPE Jr chapters.", Role.shpe_jr_chair, ["Isabela Morales", "Blake Weaver"]),
    ("Social", "Events that build community and celebrate our culture.", Role.social_chair, ["Anahi Salinas", "Samuel Avendano"]),
    ("SHPEtina", "Empowering Latinas in STEM through community and professional growth.", Role.shpetina_chair, ["Alexi Urbina", "Marylin Uriostegui"]),
    ("Web Development", "Builds and maintains the chapter website.", Role.web_dev_chair, ["Elvin Paz"]),
    ("Member Relations", "Member engagement, feedback, and retention.", Role.member_relations_chair, ["Gabriela Barreno"]),
]


# E-Board "committees" -- not real committees members can join (joinable=
# False), seeded purely so EventHost can point at an officer position or at
# the sheet's bare "eboard" owner value (the generic row, chair_role=None).
# Whoever currently holds a position's Role shows up as its "chair" the same
# way a real committee's chair does (require_chair / chair_contact_email
# aren't used here, but _sync_chair_memberships already keys purely off
# Committee.chair_role with no CHAIR_ROLES restriction, so nothing there
# needs to change).
EBOARD_COMMITTEES = [
    ("President", Role.president),
    ("Vice President External", Role.vpe),
    ("Vice President Internal", Role.vpi),
    ("Secretary", Role.secretary),
    ("Treasurer", Role.treasurer),
    ("Communications", Role.comm_director),
    ("New Member Rep", Role.new_member_rep),
    ("Regional Rep", Role.regional_rep),
    ("Director of Internal Affairs", Role.dir_int_aff),
    ("E-Board", None),
]


# The chapter's real reporting tree, from the 2026-2027 org chart. Officers
# hang off a VP; chairs hang off an officer. The president is the implicit
# root and both VPs always report to them, so neither is listed here.
# Co-chairs (the "(2)" entries on the chart) share one role, so a single link
# covers both of them.
DEFAULT_REPORTS = {
    # --- officers -> VP External ---
    Role.new_member_rep: Role.vpe,
    Role.treasurer: Role.vpe,
    Role.regional_rep: Role.vpe,
    # --- officers -> VP Internal ---
    Role.comm_director: Role.vpi,
    Role.secretary: Role.vpi,
    Role.dir_int_aff: Role.vpi,

    # --- chairs -> New Member Rep ---
    Role.social_chair: Role.new_member_rep,
    Role.member_relations_chair: Role.new_member_rep,
    # --- chairs -> Treasurer ---
    Role.eec_chair: Role.treasurer,
    Role.athletic_chair: Role.treasurer,
    Role.web_dev_chair: Role.treasurer,
    # --- chairs -> Regional Rep ---
    Role.shpe_jr_chair: Role.regional_rep,
    Role.professional_chair: Role.regional_rep,
    Role.career_fair_chair: Role.regional_rep,
    # --- chairs -> Communication Director ---
    Role.marketing_chair: Role.comm_director,
    Role.outreach_chair: Role.comm_director,
    # --- chairs -> Secretary ---
    Role.mentorshpe_chair: Role.secretary,
    Role.shpetina_chair: Role.secretary,
    # --- chairs -> Director of Internal Affairs ---
    Role.academic_chair: Role.dir_int_aff,
    Role.projects_chair: Role.dir_int_aff,
}


APPAREL_SIZES = ["S", "M", "L", "XL", "2XL"]

# The one product production genuinely needs on day one: verify-email routes a
# new member straight into dues checkout, and utils/dues.js finds this product
# BY NAME. The name therefore comes from shop_services rather than a literal —
# renaming it in one place only would break that redirect with no other symptom
# (the member just lands on the home page). Price matches the $20 tier card on
# frontend/src/pages/membershpe.jsx. Real merch is added through Shop Manager.
DUES_PRODUCT = {
    "name": DUES_PRODUCT_NAME,
    "description": "Chapter membership dues for the academic year — includes your SHPE UH chapter t-shirt plus all member benefits.",
    "price_cents": 2000,
    "product_type": ProductType.apparel,
    "sizes": APPAREL_SIZES,
}
