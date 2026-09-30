from typing import Tuple

from pydantic import BaseModel, computed_field


def split_name(name: str) -> Tuple[str, str]:
    """'Demo System Administrator' -> ('Demo', 'System Administrator'); a one-word name has no last name."""
    first, _, last = (name or "").strip().partition(" ")
    return first, last.strip()


class NameParts(BaseModel):
    """
    Adds first_name and last_name, derived from `name`, for frontends that show them separately.
    `name` stays the stored value; these are read-only views of it.
    """
    name: str

    @computed_field
    @property
    def first_name(self) -> str:
        return split_name(self.name)[0]

    @computed_field
    @property
    def last_name(self) -> str:
        return split_name(self.name)[1]
