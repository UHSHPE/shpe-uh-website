from datetime import datetime, timedelta, date
from sqlmodel import Session, select
from database import engine, create_db
import models.event      # noqa: F401
import models.committee  # noqa: F401
import models.user

from models.event import Event
from models.committee import Committee, CommitteeMembership
from models.shop.order import Order, OrderItem
from models.shop.product import Product, ProductType
from models.user.user import User
from models.user.user_schemas import UserCreate
from models.user.user_enums import ProfDev, RaceEthnicity, Role, Gender, Colleges, Classification, GPA, ExpGradDate, MembershipStatus, ShirtSize, Industry
from services.user_services import create_user

# Official committee roster. Each committee has exactly one chair role;
# co-chairs share that role and each get a CommitteeMembership with is_chair=True.
# Format: (committee name, description, chair role, [chair full names])
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


def seed_test_user(s: Session):
    # Two test members: test@ gets a PAID T-Shirt Dues order (see
    # seed_test_dues_order), test1@ has NOT paid — handy for testing the
    # dues banner and the one-per-member purchase rule side by side.
    test_members = [
        # (first, last, cougarnet, personal, psid, phone) — name fields allow
        # letters only (no digits), so the "1" lives in the email.
        ("Test", "User", "test@cougarnet.uh.edu", "test@gmail.com", "1234567", "1234567890"),
        ("Test", "Unpaid", "test1@cougarnet.uh.edu", "test1@gmail.com", "1234568", "1234567891"),
    ]
    for first_name, last_name, cougarnet_email, personal_email, psid, phone_num in test_members:
        existing_user = s.exec(
            select(User).where(User.cougarnet_email == cougarnet_email)
        ).first()

        if existing_user:
            print(f"Skipped test user {cougarnet_email} — already exists.")
            continue

        test_user = UserCreate(
            first_name=first_name,
            last_name=last_name,

            cougarnet_email=cougarnet_email,
            personal_email=personal_email,

            password="password123",

            role=Role.member,
            points=0,

            phone_num=phone_num,
            psid=psid,
            birthday=date(2000, 1, 1),

            gender=Gender.male,
            first_gen=True,

            college=Colleges.nsm,
            major="Computer Science",
            classification=Classification.senior,
            gpa=GPA.gpa_350_400,
            exp_grad_date=ExpGradDate.spring_2027,

            in_slack=True,
            is_returning=MembershipStatus.new,
            is_national_member=True,
            shirt_size=ShirtSize.m,

            race_and_ethnicity=[
                RaceEthnicity.native_american,
            ],
            prof_dev=[
                ProfDev.internships,
            ],
            interested_industries=[
                Industry.electronics,
            ],
            country_origin=[
                "Mexico",
            ],
        )

        created = create_user(s, test_user)
        created.email_verified = True  # seeded accounts skip email verification
        s.add(created)
        s.commit()
        print(f"Seeded test user {cougarnet_email}.")


def seed_test_dues_order(s: Session):
    """Mark test@cougarnet.uh.edu as dues-paid: a paid order containing the
    dues product (has_paid_dues matches on the OrderItem name snapshot).
    test1@cougarnet.uh.edu deliberately gets none — it stays unpaid."""
    from services.shop_services import DUES_PRODUCT_NAME, generate_order_code

    user = s.exec(
        select(User).where(User.cougarnet_email == "test@cougarnet.uh.edu")
    ).first()
    dues = s.exec(select(Product).where(Product.name == DUES_PRODUCT_NAME)).first()
    if user is None or dues is None:
        print("Skipped test dues order — test user or dues product missing.")
        return

    already = s.exec(
        select(OrderItem)
        .join(Order)
        .where(Order.user_id == user.id, OrderItem.product_name == DUES_PRODUCT_NAME)
    ).first()
    if already:
        print("Skipped test dues order — already exists.")
        return

    order = Order(
        order_code=generate_order_code(s),
        buyer_name=f"{user.first_name} {user.last_name}",
        buyer_email=user.personal_email,
        buyer_phone=user.phone_num or "",
        user_id=user.id,
        total_cents=dues.price_cents,
    )
    s.add(order)
    s.commit()
    s.refresh(order)
    s.add(OrderItem(
        order_id=order.id,
        product_id=dues.id,
        product_name=dues.name,
        quantity=1,
        unit_price_cents=dues.price_cents,
        size="M",
    ))
    s.commit()
    print(f"Seeded paid T-Shirt Dues order ({order.order_code}) for test@cougarnet.uh.edu.")


def chair_user_create(first_name: str, last_name: str, role: Role, idx: int) -> UserCreate:
    slug = f"{first_name}.{last_name}".lower().replace(" ", ".").replace("'", "")
    return UserCreate(
        first_name=first_name,
        last_name=last_name,

        cougarnet_email=f"{slug}@cougarnet.uh.edu",
        personal_email=f"{slug}@gmail.com",

        password="password123",

        role=role,
        points=0,

        phone_num=f"713555{1000 + idx}",
        psid=f"{2000001 + idx}",
        birthday=date(2000, 1, 1),

        gender=Gender.not_say,
        first_gen=False,

        college=Colleges.nsm,
        major="Computer Science",
        classification=Classification.senior,
        gpa=GPA.gpa_350_400,
        exp_grad_date=ExpGradDate.spring_2027,

        in_slack=True,
        is_returning=MembershipStatus.returning_1,
        is_national_member=True,
        shirt_size=ShirtSize.m,

        race_and_ethnicity=[
            RaceEthnicity.hispanic,
        ],
        prof_dev=[
            ProfDev.internships,
        ],
        interested_industries=[
            Industry.electronics,
        ],
        country_origin=[
            "United States",
        ],
    )


def seed_committees_and_chairs(s: Session):
    idx = 0
    for name, description, chair_role, chair_names in COMMITTEE_ROSTER:
        committee = s.exec(select(Committee).where(Committee.name == name)).first()
        if not committee:
            committee = Committee(name=name, description=description, chair_role=chair_role)
            s.add(committee)
            s.commit()
            s.refresh(committee)
            print(f"Seeded committee: {name}")
        else:
            print(f"Skipped committee — {name} already exists.")

        for full_name in chair_names:
            first_name, last_name = full_name.rsplit(" ", 1)
            user_data = chair_user_create(first_name, last_name, chair_role, idx)
            idx += 1

            user = s.exec(
                select(User).where(User.cougarnet_email == user_data.cougarnet_email)
            ).first()
            if not user:
                user = create_user(s, user_data)
                user.email_verified = True  # seeded accounts skip email verification
                s.add(user)
                s.commit()
                print(f"Seeded chair user: {full_name} ({chair_role.value})")
            else:
                print(f"Skipped chair user — {full_name} already exists.")

            membership = s.exec(
                select(CommitteeMembership).where(
                    CommitteeMembership.user_id == user.id,
                    CommitteeMembership.committee_id == committee.id,
                )
            ).first()
            if not membership:
                s.add(CommitteeMembership(
                    user_id=user.id,
                    committee_id=committee.id,
                    status=True,
                    is_chair=True,
                ))
                print(f"Seeded chair membership: {full_name} -> {name}")
    s.commit()


def seed_comm_director(s: Session):
    """Shop admin is held by the comms director + marketing chair roles. The
    marketing chair is already in COMMITTEE_ROSTER; comm_director is an
    e-board role, so seed one here to make that path testable."""
    existing = s.exec(
        select(User).where(User.cougarnet_email == "comms.director@cougarnet.uh.edu")
    ).first()
    if existing:
        print("Skipped comms director — already exists.")
        return

    comms = chair_user_create("Comms", "Director", Role.comm_director, 900)
    created = create_user(s, comms)
    created.email_verified = True  # seeded accounts skip email verification
    s.add(created)
    s.commit()
    print("Seeded comms director user.")


def seed_shop_settings(s: Session):
    from services.shop_services import get_shop_settings

    get_shop_settings(s)
    print("Ensured shop settings row.")


def seed_products(s: Session):
    if s.exec(select(Product)).first():
        print("Skipped products — already seeded.")
        return

    apparel_sizes = ["S", "M", "L", "XL", "2XL"]
    products = [
        # The signup flow finds this product BY NAME ("T-Shirt Dues") to send
        # new members straight into dues checkout — renaming it breaks that
        # auto-redirect (signup falls back to the home page).
        Product(
            name="T-Shirt Dues",
            description="Chapter membership dues for the academic year — includes your SHPE UH chapter t-shirt plus all member benefits.",
            price_cents=2000,
            product_type=ProductType.apparel,
            sizes=apparel_sizes,
        ),
        Product(
            name="SHPE UH Quarter-Zip",
            description="Navy quarter-zip with the embroidered SHPE UH logo. Perfect for career fairs and chilly lecture halls.",
            price_cents=4500,
            product_type=ProductType.apparel,
            sizes=apparel_sizes,
        ),
        Product(
            name="SHPE UH Sweater",
            description="Cozy crewneck sweater with the chapter wordmark across the chest.",
            price_cents=4000,
            product_type=ProductType.apparel,
            sizes=apparel_sizes,
        ),
        Product(
            name="SHPE UH Logo Sticker",
            description="Die-cut vinyl sticker of the chapter logo. Weatherproof — laptops, bottles, cars.",
            price_cents=300,
            product_type=ProductType.item,
        ),
        Product(
            name="Familia Sticker Pack",
            description="Pack of five assorted SHPE UH stickers.",
            price_cents=1000,
            product_type=ProductType.item,
        ),
    ]
    s.add_all(products)
    print(f"Seeded {len(products)} products.")


def seed_events(s: Session):
    now = datetime.utcnow()

    # Seed events (always add fresh ones relative to now)
    events = [
        Event(
            title="General Meeting",
            description="Fall kick-off general meeting. Free food provided!",
            location="SEC Auditorium",
            start_time=now + timedelta(days=1, hours=2),
            end_time=now + timedelta(days=1, hours=4),
            points_value=3,
            event_type="General Meeting",
        ),
        Event(
            title="Resume Workshop",
            description="Bring your resume for expert feedback from industry professionals.",
            location="Engineering Building Room 201",
            start_time=now + timedelta(days=3, hours=5),
            end_time=now + timedelta(days=3, hours=7),
            points_value=3,
            event_type="Professional",
        ),
        Event(
            title="STEM Outreach — Seguin Middle School",
            description="Hands-on STEM activities for 6th and 7th graders.",
            location="Seguin Middle School",
            start_time=now + timedelta(days=5, hours=4),
            end_time=now + timedelta(days=5, hours=6),
            points_value=4,
            event_type="Outreach",
        ),
    ]
    s.add_all(events)
    print("Seeded 3 events.")


def seed():
    create_db()

    with Session(engine) as s:
        seed_test_user(s)
        seed_committees_and_chairs(s)
        seed_comm_director(s)
        seed_shop_settings(s)
        seed_products(s)
        seed_test_dues_order(s)  # after products — needs the dues product
        seed_events(s)
        s.commit()

    print("Done.")


if __name__ == "__main__":
    seed()
