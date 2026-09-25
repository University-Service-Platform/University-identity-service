from enum import Enum
from typing import Optional

from pydantic import BaseModel


class AffiliationSummary(BaseModel):
    """A user's department/faculty affiliation as reported by the Directory Service."""
    department_id: str
    department_name: Optional[str] = None
    faculty_id: str
    faculty_name: Optional[str] = None


class AffiliationStatus(str, Enum):
    AVAILABLE = "AVAILABLE"            # affiliation retrieved from the Directory Service
    NONE = "NONE"                      # the Directory Service has no affiliation for this user
    UNAVAILABLE = "UNAVAILABLE"        # the Directory Service could not be reached or answered unexpectedly
    NOT_CONFIGURED = "NOT_CONFIGURED"  # DIRECTORY_SERVICE_BASE_URL is not set
