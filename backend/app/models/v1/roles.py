"""V1 platform role values stored on `v1_users.role`.

Not Spatie/legacy roles. Signup always assigns ROLE_USER.
Never accept role from public clients.
"""

from __future__ import annotations

ROLE_USER = "user"
ROLE_SUPER_ADMIN = "super_admin"
ROLE_SCHOOL_ADMIN = "school_admin"

V1_ROLES = frozenset({ROLE_USER, ROLE_SUPER_ADMIN, ROLE_SCHOOL_ADMIN})
