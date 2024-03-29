import logging
import os
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type, Union

import sanic.request

from sanic_openid_connect_provider.authorize_endpoint import authorize_handler
from sanic_openid_connect_provider.client import Client
from sanic_openid_connect_provider.handlers import (
    client_register_handler,
    jwk_handler,
    userinfo_handler,
    well_known_finger_handler,
    well_known_oauth_config_handler,
    well_known_openid_config_handler,
)
from sanic_openid_connect_provider.models.clients import ClientStore, InMemoryClientStore
from sanic_openid_connect_provider.models.code import CodeStore, InMemoryCodeStore
from sanic_openid_connect_provider.models.token import InMemoryTokenStore, TokenStore
from sanic_openid_connect_provider.models.users import UserManager
from sanic_openid_connect_provider.provider import Provider
from sanic_openid_connect_provider.token_endpoint import token_handler
from sanic_openid_connect_provider.utils import masked

__version__ = "0.0.0"


logger = logging.getLogger("oicp")


def setup_client(
    app: sanic.Sanic,
    client_id: str,
    client_secret: str,
    signature_type: str,
    callback_path: str = "/callback",
    autodiscover_base: Optional[str] = None,
    token_url: Optional[str] = None,
    authorize_url: Optional[str] = None,
    userinfo_url: Optional[str] = None,
    jwk_url: Optional[str] = None,
    access_userinfo: bool = False,
    scopes=("openid",),
    post_logon_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
) -> Client:
    if autodiscover_base is None and token_url is None:
        raise RuntimeError("Autodiscover is disabled and no token url provided")
    if autodiscover_base is None and authorize_url is None:
        raise RuntimeError("Autodiscover is disabled and no authorize url provided")
    if autodiscover_base is None and userinfo_url is None and access_userinfo:
        raise RuntimeError("Autodiscover is disabled, no userinfo url provided and access_userinfo is set to True")
    if autodiscover_base is None and jwk_url is None:
        raise RuntimeError("Autodiscover is disabled and no JWK url provided, cannot validate requests")
    if signature_type not in ("HS256", "RS256", "ES256"):
        raise RuntimeError("Signature type not one of HS256, RS256, ES256")

    # Cant check sessions is set up as they may be done in a server_startup function,
    # so we just expect them to be there.

    client_obj = Client(
        client_id=client_id,
        client_secret=client_secret,
        signature_type=signature_type,
        callback_path=callback_path,
        autodiscover_base=autodiscover_base,
        token_url=token_url,
        authorize_url=authorize_url,
        userinfo_url=userinfo_url,
        jwk_url=jwk_url,
        access_userinfo=access_userinfo,
        scopes=scopes,
        post_logon_callback=post_logon_callback,
    )

    app.add_route(client_obj.handle_callback, callback_path, frozenset({"GET", "POST"}))

    app.config["oicp_client"] = client_obj

    return client_obj


def setup_provider(
    app: sanic.Sanic,
    wellknown_openid_config_path: str = "/.well-known/openid-configuration",
    wellknown_oauth_config_path: str = "/.well-known/oauth-authorization-server",
    wellknown_finger_path: str = "/.well-known/webfinger",
    jwk_path: str = "/sso/oidc/jwk",
    userinfo_path: str = "/sso/oidc/userinfo",
    token_path: str = "/sso/oidc/token",
    authorize_path: str = "/sso/oidc/authorize",
    client_register_path: str = "/sso/oidc/client_register",
    login_funcname: str = "login",
    token_expire: int = 86400,
    code_expire: int = 86400,
    grant_type_password: bool = False,
    private_keys: List[str] = None,
    open_client_registration: bool = True,
    client_registration_key: Union[str, None, Awaitable[bool]] = None,
    user_manager_class: Union[Type[UserManager], UserManager] = UserManager,
    client_manager_class: Union[Type[ClientStore], ClientStore] = InMemoryClientStore,
    code_manager_class: Union[Type[CodeStore], CodeStore] = InMemoryCodeStore,
    token_manager_class: Union[Type[TokenStore], TokenStore] = InMemoryTokenStore,
    error_html: str = "error.html",
    autosubmit_html: str = "form-autosubmit.html",
    hidden_inputs_html: str = "hidden_inputs.html",
    authorize_html: str = "authorize.html",
) -> Provider:

    # Add our templates to the default searchpath
    if not hasattr(app, "extensions"):
        app.extensions = {}

    if "jinja2" not in app.extensions:
        raise RuntimeError("jinja2 has not been set up")

    default_template_location = os.path.join(os.path.dirname(__file__), "templates")
    app.extensions["jinja2"].env.loader.searchpath.append(default_template_location)

    app.add_route(well_known_openid_config_handler, wellknown_openid_config_path, frozenset({"GET"}))
    app.add_route(well_known_oauth_config_handler, wellknown_oauth_config_path, frozenset({"GET"}))
    app.add_route(well_known_finger_handler, wellknown_finger_path, frozenset({"GET"}))
    app.add_route(jwk_handler, jwk_path, frozenset({"GET", "OPTIONS"}))
    app.add_route(userinfo_handler, userinfo_path, frozenset({"GET", "POST", "OPTIONS"}))
    app.add_route(token_handler, token_path, frozenset({"POST"}))
    app.add_route(authorize_handler, authorize_path, frozenset({"GET", "POST"}))
    app.add_route(client_register_handler, client_register_path, frozenset({"GET", "POST"}))

    app.config["oicp_provider"] = Provider(
        user_manager_class=user_manager_class,
        client_manager_class=client_manager_class,
        code_manager_class=code_manager_class,
        token_manager_class=token_manager_class,
        login_function_name=login_funcname,
        token_expire_time=token_expire,
        code_expire_time=code_expire,
        allow_grant_type_password=grant_type_password,
        open_client_registration=open_client_registration,
        client_registration_key=client_registration_key,
        error_html=error_html,
        autosubmit_html=autosubmit_html,
        hidden_inputs_html=hidden_inputs_html,
        authorize_html=authorize_html,
    )
    app.config["oicp_provider"].load_keys(private_keys)

    return app.config["oicp_provider"]
