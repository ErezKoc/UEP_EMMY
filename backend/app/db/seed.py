"""Demo seed data so the platform is usable immediately after first boot.

Only runs when the users table is empty; a real deployment replaces this with
proper registration/auth flows and Alembic data migrations.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AgeCategory,
    Animal,
    Comment,
    Post,
    User,
    UserRole,
    VerificationStatus,
)

# All demo accounts share this password (documented in the README).
DEMO_PASSWORD = "demo1234"


def seed_demo_data(db: Session) -> None:
    if db.scalars(select(User).limit(1)).first() is not None:
        return

    owner = User(
        email="demo.owner@uepemmy.com",
        password_hash=hash_password(DEMO_PASSWORD),
        display_name="Alex the Pet Owner",
        role=UserRole.OWNER,
        bio="Proud owner of Buddy the Labrador. Learning something new about dogs every day.",
    )
    vet = User(
        email="demo.vet@uepemmy.com",
        password_hash=hash_password(DEMO_PASSWORD),
        display_name="Dr. Maya Fischer",
        role=UserRole.VETERINARIAN,
        clinic_name="Riverside Veterinary Clinic",
        license_number="VET-2024-0042",
        bio="Small-animal veterinarian with 12 years of experience. Special interest in nutrition and preventive care.",
        # Pre-verified so the demo shows the badge without a review round.
        verification_status=VerificationStatus.VERIFIED,
    )
    # Second vet left unverified so the difference is visible in the demo, and
    # so there is something to approve in the admin queue.
    pending_vet = User(
        email="demo.newvet@uepemmy.com",
        password_hash=hash_password(DEMO_PASSWORD),
        display_name="Dr. Deniz Aydın",
        role=UserRole.VETERINARIAN,
        clinic_name="Anatolia Animal Hospital",
        license_number="VET-2026-0117",
        bio="Newly joined veterinarian focusing on dermatology.",
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
    db.add_all([post_food, post_checkup])
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
    db.commit()


ADMIN_EMAIL = "admin@uepemmy.com"


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
        )
    )
    db.commit()
