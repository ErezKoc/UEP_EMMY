"""Emergency numbers an owner can call when no clinic is open.

Same discipline as the triage rule table next door: every entry names the page
it came from and the date that page was read, because a wrong number on this
list is worse than no list at all — it is a delay at the one moment delay
costs most.

Nothing here is a substitute for a veterinary practice. These are the services
that answer when yours does not, and the wording says so rather than presenting
them as an alternative to being seen.

NOT REVIEWED BY A VETERINARIAN. The numbers were read from the publishers' own
pages on the dates recorded; nobody on the team has phoned them to confirm.
"""

from dataclasses import dataclass
from datetime import date

READ_ON = date(2026, 8, 23)


@dataclass(frozen=True)
class EmergencyContact:
    """One service, its number, and where we got the number."""

    #: What this service is, in the owner's terms.
    name: str
    #: As published, including formatting — an owner reads it off the screen.
    phone: str
    #: `tel:` target. Kept separate because the printed form is not dialable.
    dial: str
    #: When to use it, and when not to.
    when: str
    #: Anything an owner should know before dialling, including cost.
    caveat: str | None
    source_name: str
    source_url: str
    accessed: date = READ_ON
    #: Where the service operates. Named because both entries below are US
    #: services and this platform's users are not all in the US; the UI says so
    #: rather than implying a number works everywhere.
    coverage: str = "United States"


EMERGENCY_CONTACTS: tuple[EmergencyContact, ...] = (
    EmergencyContact(
        name="ASPCA Animal Poison Control Center",
        phone="(888) 426-4435",
        dial="+18884264435",
        when=(
            "If your pet may have eaten, breathed in, or touched something poisonous. "
            "Call before doing anything else — some first aid makes poisoning worse."
        ),
        caveat="Available 24/7, 365 days a year. A consultation fee may apply.",
        source_name="ASPCA Animal Poison Control Center",
        source_url="https://www.aspca.org/pet-care/animal-poison-control",
    ),
    EmergencyContact(
        name="Pet Poison Helpline",
        phone="(855) 764-7661",
        dial="+18557647661",
        when="A second poison service, for when the line above is busy.",
        caveat="Available 24/7.",
        source_name="Pet Poison Helpline",
        source_url=(
            "https://www.petpoisonhelpline.com/pet-owners/basics/"
            "signs-of-poisoning-in-dogs-and-cats/"
        ),
    ),
)

#: Said above the list, every time it is shown.
#:
#: The list is short and both entries are American, which is a limitation an
#: owner has to be told about rather than left to discover mid-emergency. It
#: also states the thing a poison line cannot do, because an owner reading a
#: page headed "emergency numbers" may reasonably think it is the whole answer.
EMERGENCY_NOTE = (
    "These services advise on poisoning; they cannot examine your pet. If your pet is "
    "collapsed, struggling to breathe, bleeding heavily, or seizing, go to a veterinary "
    "clinic or an out-of-hours emergency service now. Both numbers below are United States "
    "services — outside the US, use your own country's animal poison line and your practice's "
    "out-of-hours number."
)
