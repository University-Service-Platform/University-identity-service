"""
The synthetic demo accounts every team tests with, and the guard that keeps them unchanged.

The demo logins are shared across all groups, so one tester changing a demo user's password,
roles or status breaks everyone else's testing. While PROTECT_DEMO_USERS is on (the default),
the API refuses to modify or delete these accounts. Other accounts are unaffected, so user
management can still be exercised on accounts testers create themselves.
"""
from dataclasses import dataclass
from typing import FrozenSet, List

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.models.user import AccountStatus, AccountType


@dataclass(frozen=True)
class DemoUser:
    id: str
    university_id: str
    name: str
    account_type: AccountType
    role: str
    status: AccountStatus = AccountStatus.ACTIVE

    @property
    def email(self) -> str:
        return f"{self.university_id.lower()}@university.example"


DEMO_USERS: List[DemoUser] = [
    DemoUser("usr-admin-001", "ADM001", "Demo System Administrator", AccountType.STAFF, "ADMIN"),
    DemoUser("usr-staff-001", "STF001", "Demo Staff Member", AccountType.STAFF, "STAFF"),
    DemoUser("usr-student-001", "STU001", "Demo Student", AccountType.STUDENT, "STUDENT"),
    DemoUser("usr-student-002", "STU002", "Demo Inactive Student", AccountType.STUDENT, "STUDENT",
             AccountStatus.INACTIVE),
    # A second active student, for department checks that need students in different departments
    DemoUser("usr-student-003", "STU003", "Demo Student (Second Department)", AccountType.STUDENT, "STUDENT"),
    DemoUser("usr-academic-001", "ACD001", "Demo Academic Staff", AccountType.STAFF, "ACADEMIC_STAFF"),
    DemoUser("usr-adminstaff-001", "ADS001", "Demo Administrative Staff", AccountType.STAFF, "ADMINISTRATIVE_STAFF"),
    DemoUser("usr-servicedesk-001", "SDO001", "Demo Service Desk Officer", AccountType.STAFF, "SERVICE_DESK_OFFICER"),
    DemoUser("usr-technician-001", "TEC001", "Demo Technician", AccountType.STAFF, "TECHNICIAN"),
    DemoUser("usr-resourcemgr-001", "RMG001", "Demo Resource Manager", AccountType.STAFF, "RESOURCE_MANAGER"),
    DemoUser("usr-organizer-001", "EVO001", "Demo Event Organizer", AccountType.STAFF, "EVENT_ORGANIZER"),
]

# Both identifiers, since the API accepts a user ID or a university ID in the path
PROTECTED_IDENTIFIERS: FrozenSet[str] = frozenset(
    {d.id.lower() for d in DEMO_USERS} | {d.university_id.lower() for d in DEMO_USERS}
)


def ensure_not_protected_demo_account(identifier: str) -> None:
    """Refuse (403 DEMO_ACCOUNT_PROTECTED) to change a shared demo account while protection is on."""
    if get_settings().protect_demo_users and identifier.strip().lower() in PROTECTED_IDENTIFIERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"success": False, "error": {
                "code": "DEMO_ACCOUNT_PROTECTED",
                "message": "Shared demo accounts can't be changed or deleted, so every team can keep testing "
                           "with them. Create your own account to test user management."}}
        )
