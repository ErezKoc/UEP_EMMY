"""The emergency contact list, as the client receives it."""

from datetime import date

from pydantic import BaseModel, ConfigDict


class EmergencyContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    #: As published — an owner reads this off the screen and dials it by hand.
    phone: str
    #: The `tel:` target, which is not the same string as the one above.
    dial: str
    when: str
    caveat: str | None
    coverage: str
    #: Carried to the client so the number can be shown with the page it came
    #: from. A phone number with no provenance is exactly the kind of thing that
    #: rots quietly, and this list is not one to let rot.
    source_name: str
    source_url: str
    accessed: date


class EmergencyContactsRead(BaseModel):
    #: Shown above the list, always. It says what these services cannot do.
    note: str
    contacts: list[EmergencyContactRead]
