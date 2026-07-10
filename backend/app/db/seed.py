"""Demo seed data so the platform is usable immediately after first boot.

Only runs when the users table is empty; a real deployment replaces this with
proper registration/auth flows and Alembic data migrations.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgeCategory, Animal, Comment, Post, User, UserRole


def seed_demo_data(db: Session) -> None:
    if db.scalars(select(User).limit(1)).first() is not None:
        return

    owner = User(
        email="demo.owner@uep-emmy.local",
        display_name="Alex the Pet Owner",
        role=UserRole.OWNER,
    )
    vet = User(
        email="demo.vet@uep-emmy.local",
        display_name="Dr. Maya Fischer",
        role=UserRole.VETERINARIAN,
        clinic_name="Riverside Veterinary Clinic",
        license_number="VET-2024-0042",
    )
    db.add_all([owner, vet])
    db.flush()

    buddy = Animal(
        name="Buddy",
        species="dog",
        breed="Labrador Retriever",
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
