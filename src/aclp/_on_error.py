from typing import Literal, TypeAlias

OnError: TypeAlias = Literal["allow", "deny"]

FAIL_CLOSED_METHODS: tuple[str, ...] = ("tool.requested", "permission.requested")


def on_error_for(method: str, configured: OnError | None = None) -> OnError:
    """What a failed request for `method` does to the continuation it guards.

    The configured policy wins; without one, `tool.requested` and `permission.requested` deny
    and every other method allows. Notifications never guard a continuation.

    >>> on_error_for("tool.requested"), on_error_for("input.submitted")
    ('deny', 'allow')
    >>> on_error_for("tool.requested", "allow")
    'allow'
    """
    if configured is not None:
        return configured

    return "deny" if method in FAIL_CLOSED_METHODS else "allow"
