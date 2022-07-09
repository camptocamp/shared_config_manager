import os
from typing import Optional, Union

import c2cwsgiutils.auth
import pyramid.request
from pyramid.security import Allowed, Denied

from shared_config_manager.configuration import SourceConfig


class User:
    login: Optional[str]
    name: Optional[str]
    url: Optional[str]
    is_auth: bool
    token: Optional[str]
    is_admin: bool
    request: pyramid.request.Request

    def __init__(
        self,
        login: Optional[str],
        name: Optional[str],
        url: Optional[str],
        is_auth: bool,
        token: Optional[str],
        request: pyramid.request.Request,
    ) -> None:
        self.login = login
        self.name = name
        self.url = url
        self.is_auth = is_auth
        self.token = token
        self.request = request
        self.is_admin = c2cwsgiutils.auth.check_access(
            self.request,
            os.environ["C2C_AUTH_GITHUB_REPOSITORY"],
            os.environ.get("C2C_AUTH_GITHUB_ACCESS_TYPE", "admin"),
        )

    def has_access(self, source_config: SourceConfig) -> bool:
        if self.is_admin:
            return True

        auth_config = source_config.get("auth", {})
        if "github_repository" in auth_config:
            return (
                c2cwsgiutils.auth.check_access(
                    self.request,
                    auth_config["github_repository"],
                    auth_config.get("github_access_type", "push"),
                )
                or self.is_admin
            )

        return False


class SecurityPolicy:
    def identity(self, request: pyramid.request.Request) -> User:
        """Return app-specific user object."""

        if not hasattr(request, "user"):
            is_auth, user = c2cwsgiutils.auth.is_auth_user(request)
            if is_auth:
                setattr(
                    request,
                    "user",
                    User(
                        user.get("login"),
                        user.get("name"),
                        user.get("url"),
                        is_auth,
                        user.get("token"),
                        request,
                    ),
                )
            else:
                setattr(request, "user", None)

        return request.user  # type: ignore

    def authenticated_userid(self, request: pyramid.request.Request) -> Optional[str]:
        """Return a string ID for the user."""

        identity = self.identity(request)

        if identity is None:
            return None

        return identity.login

    def permits(
        self, request: pyramid.request.Request, context: SourceConfig, permission: str
    ) -> Union[Allowed, Denied]:
        """Allow access to everything if signed in."""

        identity = self.identity(request)

        if identity is None:
            return Denied("User is not signed in.")
        if identity.is_admin:
            return Allowed("The User is admin.")
        if permission == "all":
            return Denied("Root access is required.")
        if identity.has_access(context):
            return Allowed(f"The User has access to source {permission}.")
        return Denied(f"The User has no access to source {permission}.")
