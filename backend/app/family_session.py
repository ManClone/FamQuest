"""Connect an authenticated central principal to its isolated family database.

Authentication and family resolution happen before this function is called.
The database identifier comes from the trusted registry, never request input.
"""

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.family_db import FamilyDatabase, FamilyDatabaseRouter
from app.family_principal import FamilyPrincipal


def open_principal_family_session(
    router: FamilyDatabaseRouter, principal: FamilyPrincipal
) -> Iterator[Session]:
    if principal.role not in {"admin", "parent", "child"}:
        raise PermissionError("Invalid family role")
    family = FamilyDatabase(
        family_id=principal.tenant_id, database_name=principal.database_name
    )
    with router.session(family) as session:
        yield session
