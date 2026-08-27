"""Demo seed data so the platform is usable immediately after first boot.

Only runs when the users table is empty; a real deployment replaces this with
proper registration/auth flows and Alembic data migrations.
"""

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AgeCategory,
    Animal,
    Comment,
    Post,
    ReportReason,
    ReportStatus,
    ReportTargetType,
    User,
    UserReport,
    UserRole,
    VerificationStatus,
)

# All demo accounts share this password (documented in the README).
DEMO_PASSWORD = "demo1234"

#: Demo accounts are created already confirmed.
#:
#: Signing in needs a confirmed address, and these fixtures have addresses at
#: `@uepemmy.com` that nobody can read - so without this the seeded logins the
#: README documents would all be refused, and a fresh checkout would have no way
#: in at all. Real accounts still confirm theirs; these are not real accounts.
def _seeded_verification_time() -> datetime:
    return datetime.now(timezone.utc)


def seed_demo_data(db: Session) -> None:
    if db.scalars(select(User).limit(1)).first() is not None:
        return

    owner = User(
        email="demo.owner@uepemmy.com",
        password_hash=hash_password(DEMO_PASSWORD),
        email_verified_at=_seeded_verification_time(),
        display_name="Alex the Pet Owner",
        role=UserRole.OWNER,
        bio="Proud owner of Buddy the Labrador. Learning something new about dogs every day.",
    )
    vet = User(
        email="demo.vet@uepemmy.com",
        password_hash=hash_password(DEMO_PASSWORD),
        email_verified_at=_seeded_verification_time(),
        display_name="Dr. Maya Fischer",
        role=UserRole.VETERINARIAN,
        clinic_name="Riverside Veterinary Clinic",
        license_number="VET-2024-0042",
        bio="Small-animal veterinarian with 12 years of experience. Special interest in nutrition and preventive care.",
        clinic_phone="(555) 014-2280",
        clinic_emergency_phone="(555) 014-2299",
        clinic_email="reception@riversidevetclinic.example",
        clinic_website="https://riversidevetclinic.example",
        clinic_address_line="118 Riverside Drive",
        clinic_city="Portland",
        clinic_postcode="97205",
        clinic_country="United States",
        clinic_hours="Mon-Fri 08:00-18:00, Sat 09:00-13:00. Closed Sundays.",
        # The demo needs one practice that answers requests and one that does
        # not, or the button's absence looks like a bug rather than a setting.
        accepts_appointments=True,
        # Pre-verified so the demo shows the badge without a review round.
        verification_status=VerificationStatus.VERIFIED,
    )
    # Second vet left unverified so the difference is visible in the demo, and
    # so there is something to approve in the admin queue.
    pending_vet = User(
        email="demo.newvet@uepemmy.com",
        password_hash=hash_password(DEMO_PASSWORD),
        email_verified_at=_seeded_verification_time(),
        display_name="Dr. Deniz Aydın",
        role=UserRole.VETERINARIAN,
        clinic_name="Anatolia Animal Hospital",
        license_number="VET-2026-0117",
        bio="Newly joined veterinarian focusing on dermatology.",
        clinic_phone="+90 312 555 0142",
        clinic_email="info@anatoliaanimalhospital.example",
        clinic_address_line="Kizilay Caddesi 42",
        clinic_city="Ankara",
        clinic_postcode="06420",
        clinic_country="Turkiye",
        clinic_hours="Every day 09:00-19:00.",
    )
    db.add_all([owner, vet, pending_vet])
    db.flush()

    buddy = Animal(
        name="Buddy",
        species="dog",
        breed="Labrador Retriever",
        birth_date=date(2021, 3, 14),
        age_category=AgeCategory.ADULT,
        owner_id=owner.id,
    )
    db.add(buddy)

    post_food = Post(
        title="How much should an adult Labrador eat per day?",
        content=(
            "Buddy is a 5-year-old Lab, around 30 kg, and he acts hungry all the "
            "time. The bag says 350 g/day but he inhales it in seconds. Is it okay "
            "to give him more, or are Labs just like this?"
        ),
        author_id=owner.id,
    )
    post_checkup = Post(
        title="Reminder: senior pets benefit from twice-yearly checkups",
        content=(
            "A note from the clinic side: once dogs and cats reach their senior "
            "years, annual exams often miss slow-developing issues like kidney "
            "disease or dental pain. Twice-yearly visits with basic bloodwork "
            "catch these far earlier. Happy to answer questions in the comments."
        ),
        author_id=vet.id,
    )
    # Written by the *unverified* veterinarian and deliberately reportable, so
    # the moderation queue has something realistic to review out of the box.
    post_dosing = Post(
        title="Just give your dog human painkillers, it is the same molecule",
        content=(
            "Honestly you do not need a clinic visit for limping. Take whatever "
            "ibuprofen you have at home and give half a tablet, works every time. "
            "Trust me, I am a vet and I do this with all my patients."
        ),
        author_id=pending_vet.id,
    )
    db.add_all([post_food, post_checkup, post_dosing])
    db.flush()

    db.add(
        Comment(
            post_id=post_food.id,
            author_id=vet.id,
            content=(
                "Labs are famously food-motivated, so appetite alone isn't a good "
                "guide. Stick close to the feeding table for his target weight and "
                "use his body condition score, not his enthusiasm, to adjust."
            ),
        )
    )

    db.add(
        UserReport(
            reporter_id=owner.id,
            reported_user_id=pending_vet.id,
            target_type=ReportTargetType.POST,
            post_id=post_dosing.id,
            content_snapshot=f"{post_dosing.title}\n\n{post_dosing.content}",
            reasons=[
                ReportReason.HARMFUL_ADVICE.value,
                ReportReason.IMPERSONATING_VET.value,
            ],
            details=(
                "Ibuprofen is toxic to dogs — this could kill someone's pet. This "
                "account also claims to be a vet but has no verified badge."
            ),
            status=ReportStatus.PENDING,
        )
    )
    db.commit()


ADMIN_EMAIL = "admin@uepemmy.com"

#: The fixture accounts, by address. Nobody can read any of these inboxes.
SEEDED_ACCOUNTS = (
    "demo.owner@uepemmy.com",
    "demo.vet@uepemmy.com",
    "demo.newvet@uepemmy.com",
    ADMIN_EMAIL,
)


def ensure_seeded_accounts_verified(db: Session) -> int:
    """Keep the demo logins working now that signing in needs a confirmed address.

    Runs on every boot, like `ensure_admin_account`, and for the same reason:
    `seed_demo_data` only fires on an empty database, so a deployment that
    already had these accounts would never get the flag any other way.

    Deterministic rather than clever. It matches the four fixture addresses by
    name instead of guessing which accounts predate the rule - a heuristic like
    "confirm everybody if nobody is confirmed yet" would, on a fresh
    deployment, silently confirm the first real person who signed up and never
    clicked their link. That is the whole rule undone by its own migration.

    Real accounts are untouched. They confirm their address the ordinary way,
    and with no SMTP server the link is still readable:
    `python -m app.scripts.outbox --links`.
    """
    accounts = db.scalars(
        select(User).where(
            User.email.in_(SEEDED_ACCOUNTS), User.email_verified_at.is_(None)
        )
    ).all()
    if not accounts:
        return 0
    stamp = _seeded_verification_time()
    for account in accounts:
        account.email_verified_at = stamp
    db.commit()
    return len(accounts)


def ensure_admin_account(db: Session) -> None:
    """Create the credential-review admin if the platform has none.

    Unlike `seed_demo_data` this runs on every boot: veterinarian verification
    needs a reviewer, and databases created before the admin role existed have
    no way to get one otherwise.
    """
    existing = db.scalars(select(User).where(User.role == UserRole.ADMIN).limit(1)).first()
    if existing is not None:
        return

    db.add(
        User(
            email=ADMIN_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            display_name="Platform Admin",
            role=UserRole.ADMIN,
            bio="Reviews veterinarian credentials.",
            # Confirmed on creation, like the other fixtures: nobody can read
            # admin@uepemmy.com, and an admin who cannot sign in leaves every
            # veterinarian verification stuck in the queue forever.
            email_verified_at=_seeded_verification_time(),
        )
    )
    db.commit()


#: The practice details the two demo veterinarians advertise.
#:
#: Kept beside `seed_demo_data`'s definitions rather than inside them because
#: `ensure_demo_clinic_details` below has to be able to apply them to accounts
#: that already exist — see its docstring.
_DEMO_CLINIC_DETAILS: dict[str, dict[str, object]] = {
    "demo.vet@uepemmy.com": {
        "clinic_phone": "(555) 014-2280",
        "clinic_emergency_phone": "(555) 014-2299",
        "clinic_email": "reception@riversidevetclinic.example",
        "clinic_website": "https://riversidevetclinic.example",
        "clinic_address_line": "118 Riverside Drive",
        "clinic_city": "Portland",
        "clinic_postcode": "97205",
        "clinic_country": "United States",
        "clinic_hours": "Mon-Fri 08:00-18:00, Sat 09:00-13:00. Closed Sundays.",
        "accepts_appointments": True,
    },
    "demo.newvet@uepemmy.com": {
        "clinic_phone": "+90 312 555 0142",
        "clinic_email": "info@anatoliaanimalhospital.example",
        "clinic_address_line": "Kizilay Caddesi 42",
        "clinic_city": "Ankara",
        "clinic_postcode": "06420",
        "clinic_country": "Turkiye",
        "clinic_hours": "Every day 09:00-19:00.",
        # Left off deliberately, so the directory shows both states.
        "accepts_appointments": False,
    },
}


def ensure_demo_clinic_details(db: Session) -> None:
    """Fill in the demo vets' practice details if they are still blank.

    Runs on every boot, for the same reason `ensure_admin_account` does:
    `seed_demo_data` returns early the moment any user exists, so every
    database created before these columns existed — including a Docker volume
    that has been carried across rebuilds — would show the demo veterinarians
    with no phone number and no address forever.

    Only ever writes into a field that is empty, and only on the two seeded demo
    accounts. A practice that has edited its own details keeps them, and nothing
    here can overwrite a real clinic's phone number with a made-up one.
    """
    for email, details in _DEMO_CLINIC_DETAILS.items():
        vet = db.scalars(select(User).where(User.email == email)).first()
        if vet is None:
            continue
        for field, value in details.items():
            # `accepts_appointments` is a boolean and False is a legitimate
            # stored value, so "is it blank" is only asked of the text fields.
            if isinstance(value, bool):
                continue
            if not getattr(vet, field, None):
                setattr(vet, field, value)
        # Set only while it is still off, so a practice that turned it off stays off.
        if details.get("accepts_appointments") and not vet.accepts_appointments:
            vet.accepts_appointments = True
    db.commit()
