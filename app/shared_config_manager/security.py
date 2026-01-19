import hashlib
import hmac
import logging
from typing import Annotated

import c2casgiutils.auth
import c2casgiutils.config
from fastapi import Depends, Header, Request

from shared_config_manager import config
from shared_config_manager.configuration import SourceConfig

_LOG = logging.getLogger(__name__)


class User:
    """User object for the application."""

    auth_type: str
    login: str | None
    name: str | None
    url: str | None
    is_auth: bool
    token: str | None

    def __init__(
        self,
        auth_type: str,
        login: str | None = None,
        name: str | None = None,
        url: str | None = None,
        is_auth: bool = False,
        token: str | None = None,
        auth_info: c2casgiutils.auth.AuthInfo | None = None,
    ) -> None:
        self.auth_type = auth_type
        self.login = login
        self.name = name
        self.url = url
        self.is_auth = is_auth
        self.token = token
        self.auth_info = auth_info

    async def is_admin(self) -> bool:
        return (
            await c2casgiutils.auth.check_access(self.auth_info, {})
            if self.token is not None and self.auth_info is not None
            else False
        )

    async def has_access(self, source_config: SourceConfig) -> bool:
        if await self.is_admin():
            return True

        auth_config = source_config.get("auth", {})
        if "github_repository" in auth_config and self.auth_info is not None:
            return await c2casgiutils.auth.check_access(self.auth_info, auth_config)

        return False


async def get_identity(
    request: Request,
    auth_info: Annotated[c2casgiutils.auth.AuthInfo, Depends(c2casgiutils.auth.get_auth)],
    x_hub_signature_256: str | None = Header(default=None),
    x_scm_secret: str | None = Header(default=None),
) -> User | None:
    """
    FastAPI dependency to get the identity.
    """
    if c2casgiutils.config.settings.auth.test.username is not None:
        return User(
            auth_type="test_user",
            login=auth_info.user.login,
            name=auth_info.user.display_name,
            url=auth_info.user.url,
            is_auth=auth_info.is_logged_in,
            token=auth_info.user.token,
            auth_info=auth_info,
        )
    if x_hub_signature_256 is not None and config.settings.github_secret is not None:
        body = await request.body()
        our_signature = hmac.new(
            key=config.settings.github_secret.encode("utf-8"),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(
            our_signature,
            x_hub_signature_256.split("=", 1)[1],
        ):
            return User("github_webhook", is_auth=True, auth_info=auth_info)
        _LOG.warning("Invalid GitHub signature")
        _LOG.debug(
            """Incorrect GitHub signature
GitHub signature: %s
Our signature: %s
Content length: %i
body:
%s
---""",
            x_hub_signature_256,
            our_signature,
            len(body),
            body,
        )

    elif x_scm_secret is not None and config.settings.secret is not None:
        if x_scm_secret == config.settings.secret:
            return User("scm_internal", is_auth=True, auth_info=auth_info)
        _LOG.warning("Invalid SCM secret")

    elif auth_info.is_logged_in:
        return User(
            "github_oauth",
            auth_info.user.login,
            auth_info.user.display_name,
            auth_info.user.url,
            auth_info.is_logged_in,
            auth_info.user.token,
            auth_info=auth_info,
        )

    return None


class Allowed:
    """Allowed access."""

    def __init__(self, reason: str) -> None:
        self.reason = reason


class Denied:
    """Denied access."""

    def __init__(self, reason: str) -> None:
        self.reason = reason


async def permits(
    identity: User | None,
    context: SourceConfig | None,
    permission: str,
) -> Allowed | Denied:
    """Allow access to everything if signed in."""
    if identity is None:
        return Denied("User is not signed in.")
    if identity.auth_type in ("github_webhook", "scm_internal", "test_user"):
        return Allowed(f"All access auth type: {identity.auth_type}")
    if await identity.is_admin():
        return Allowed("The User is admin.")
    if permission == "all":
        return Denied("Root access is required.")
    if context is not None and await identity.has_access(context):
        return Allowed(f"The User has access to source {permission}.")
    return Denied(f"The User has no access to source {permission}.")
