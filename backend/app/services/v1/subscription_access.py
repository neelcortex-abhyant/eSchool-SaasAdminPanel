"""Isolated subscription-access decision. The default does not block anyone.

The product has not named which subscription statuses, if any, should stop a
School Admin or a legacy school route. School activation stays on
schools.status and schools.installed. This function is the only place that
decision should be added later. Until then it ignores subscription rows.
"""

from __future__ import annotations


def subscription_expiry_blocks_access(school_id: int | None) -> bool:
    """Return whether this school should be denied because of a subscription.

    ``school_id`` is accepted so a later rule can load that school's
    subscriptions. The current rule does not read them and does not block.
    """
    del school_id
    return False
