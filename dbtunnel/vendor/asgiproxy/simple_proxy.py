import functools
from dataclasses import dataclass
from pathlib import Path

from enum import Enum

from cachetools import TTLCache
from databricks.sdk import WorkspaceClient
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from dbtunnel.vendor.asgiproxy.context import ProxyContext
from dbtunnel.vendor.asgiproxy.proxies.http import proxy_http
from dbtunnel.vendor.asgiproxy.proxies.websocket import proxy_websocket


DB_TUNNEL_LOGIN_PATH = "/dbtunnel/login"

@functools.lru_cache(maxsize=0)
def get_login_content(*,
                      root_path: str,
                      workspace_url: str,
                      user_name: str):
    from dbtunnel.vendor.asgiproxy import templates
    templates_directory = Path(templates.__file__).parent

    # Construct the path to the login.html file
    login_html_path = templates_directory / 'login.html'

    with open(str(login_html_path), "r") as file:
        # root path needs right slash trimmed off
        return file.read().format(workspace_url=workspace_url,
                                  root_path=root_path.rstrip("/"),
                                  login_path=DB_TUNNEL_LOGIN_PATH,
                                  user_name=user_name)


@dataclass
class DatabricksProxyHeaders:
    user_id: str
    user_name: str


def get_databricks_user_header(scope: Scope) -> DatabricksProxyHeaders:
    hdrs = DatabricksProxyHeaders(user_id="", user_name="")
    for header in scope["headers"]:
        key = header[0].decode("utf-8")
        if key.lower() == "x-databricks-user-name":
            hdrs.user_name = header[1].decode("utf-8")
        if key.lower() == "x-databricks-user-id":
            hdrs.user_id = header[1].decode("utf-8")
    return hdrs

def validate_user(url: str, user: str, token: str) -> bool:
    try:
        w = WorkspaceClient(
            host=url,
            token=token
        )
        return w.current_user.me().user_name == user
    except Exception:
        return False

# Simple state machine, user is not in authloop when ttl cache has their email with token
class AuthLoopState(Enum):
    StillInAuthLoop = "STILL_IN_AUTH_LOOP"
    NotInAuthLoop = "NOT_IN_AUTH_LOOP"

async def handle_token_auth(
        proxy_context: ProxyContext,
        cache: TTLCache,
        scope: Scope,
        send: Send,
        receive: Receive):

    workspace_url = proxy_context.config.token_auth_workspace_url
    root_path = scope["root_path"]
    if scope["path"].startswith(root_path):
        scope["path"] = scope["path"].replace(root_path, "")
    dbx_ctx_headers = get_databricks_user_header(scope)
    login_page_content = get_login_content(
                    workspace_url=workspace_url,
                    user_name=dbx_ctx_headers.user_name,
                    root_path=root_path
                )

    if scope["path"] == DB_TUNNEL_LOGIN_PATH:
        request = Request(scope, receive)
        content = await request.form()
        user = content.get("userName") or dbx_ctx_headers.user_name
        workspace_url = content.get("workspaceUrl") or workspace_url
        password = content.get("token")
        # user accidentally clicks form
        if user is None and password is None:
            # this is root path with respect to asgi app root path
            resp = RedirectResponse(url="/", status_code=302)
            await resp(scope, receive, send)
            return AuthLoopState.StillInAuthLoop
        # invalid user
        if validate_user(workspace_url, user, password) is False:
            resp = Response(
                content=login_page_content, status_code=401
            )
            await resp(scope, receive, send)
            return AuthLoopState.StillInAuthLoop

        cache[user] = password
        # this is root path with respect to asgi app root path
        resp = RedirectResponse(url="/", status_code=302)
        await resp(scope, receive, send)
        return AuthLoopState.StillInAuthLoop

    if cache.get(dbx_ctx_headers.user_name) is None:
        resp = Response(
            content=login_page_content, status_code=200
        )
        await resp(scope, receive, send)
        return AuthLoopState.StillInAuthLoop
    
    return AuthLoopState.NotInAuthLoop


def make_simple_proxy_app(
        proxy_context: ProxyContext,
        login_timeout: int = 3600,
        *,
        proxy_http_handler=proxy_http,
        proxy_websocket_handler=proxy_websocket,
) -> ASGIApp:
    """
    Given a ProxyContext, return a simple ASGI application that can proxy
    HTTP and WebSocket connections.

    The handlers for the protocols can be overridden and/or removed with the
    respective parameters.
    """

    # we assume there is not going to be more than 250k users
    cache = TTLCache(maxsize=250000, ttl=login_timeout) # just dont use it if auth not needed

    async def app(scope: Scope, receive: Receive, send: Send):  # noqa: ANN201


        if scope["type"] == "lifespan":
            return None  # We explicitly do nothing here for this simple app.

        if proxy_context.config.token_auth_workspace_url is not None and proxy_context.config.token_auth is True:
            resp = await handle_token_auth(proxy_context, cache, scope, send, receive)
            if resp == AuthLoopState.StillInAuthLoop:
                return None

        if scope["type"] == "http" and proxy_http_handler:
            return await proxy_http_handler(
                context=proxy_context, scope=scope, receive=receive, send=send
            )

        if scope["type"] == "websocket" and proxy_websocket_handler:
            return await proxy_websocket_handler(
                context=proxy_context, scope=scope, receive=receive, send=send
            )

        raise NotImplementedError(f"Scope {scope} is not understood")

    return app
