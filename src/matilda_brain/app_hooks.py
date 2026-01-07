"""
Hook implementations for Matilda Brain - Text to Text.

This file contains the business logic for your CLI commands.
Implement the hook functions below to handle your CLI commands.

IMPORTANT: Hook names must use snake_case with 'on_' prefix
Example:
- Command 'hello' -> Hook function 'on_hello'
- Command 'hello-world' -> Hook function 'on_hello_world'
"""

# Import any modules you need here
from typing import Any, Dict, Optional

from matilda_brain.internal import hooks as brain_hooks


def on_ask(
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tools: Optional[bool] = None,
    session: Optional[str] = None,
    system: Optional[str] = None,
    stream: Optional[bool] = None,
    json: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    return brain_hooks.on_ask(
        command_name="ask",
        prompt=(prompt,) if prompt else tuple(),
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        tools=tools,
        session=session,
        system=system,
        stream=stream,
        json=json,
        **kwargs,
    )


def on_chat(
    model: Optional[str] = None,
    session: Optional[str] = None,
    tools: Optional[bool] = None,
    markdown: Optional[bool] = None,
    **kwargs,
) -> Dict[str, Any]:
    return brain_hooks.on_chat(
        command_name="chat",
        model=model,
        session=session,
        tools=tools,
        markdown=markdown,
        **kwargs,
    )


def on_stateless(
    message: Optional[str] = None,
    system: Optional[str] = None,
    history: Optional[str] = None,
    tools: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **kwargs,
) -> Dict[str, Any]:
    return brain_hooks.on_stateless(
        command_name="stateless",
        message=(message,) if message else tuple(),
        system=system,
        history=history,
        tools=tools,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )


def on_list(
    resource: Optional[str] = None,
    format: Optional[str] = None,
    show_secrets: Optional[bool] = None,
    show_disabled: Optional[bool] = None,
    **kwargs,
) -> None:
    if show_secrets is not None:
        return brain_hooks.on_config_list(command_name="config list", show_secrets=show_secrets, **kwargs)
    if show_disabled is not None:
        return brain_hooks.on_tools_list(command_name="tools list", show_disabled=show_disabled, **kwargs)
    return brain_hooks.on_list(command_name="list", resource=resource, format=format or "table", **kwargs)


def on_get(key: str, **kwargs) -> None:
    return brain_hooks.on_config_get(command_name="config get", key=key, **kwargs)


def on_set(key: str, value: str, **kwargs) -> None:
    return brain_hooks.on_config_set(command_name="config set", key=key, value=value, **kwargs)


def on_enable(tool_name: str, **kwargs) -> None:
    return brain_hooks.on_tools_enable(command_name="tools enable", tool_name=tool_name, **kwargs)


def on_disable(tool_name: str, **kwargs) -> None:
    return brain_hooks.on_tools_disable(command_name="tools disable", tool_name=tool_name, **kwargs)


def on_status(json: bool = False, **kwargs) -> Dict[str, Any]:
    return brain_hooks.on_status(command_name="status", json=json, **kwargs)


def on_models(json: bool = False, **kwargs) -> Dict[str, Any]:
    return brain_hooks.on_models(command_name="models", json=json, **kwargs)


def on_info(model: Optional[str] = None, json: bool = False, **kwargs) -> Dict[str, Any]:
    return brain_hooks.on_info(command_name="info", model=model, json=json, **kwargs)


def on_export(
    session: Optional[str] = None,
    format: Optional[str] = None,
    output: Optional[str] = None,
    include_metadata: Optional[bool] = None,
    **kwargs,
) -> Dict[str, Any]:
    return brain_hooks.on_export(
        command_name="export",
        session=session,
        format=format,
        output=output,
        include_metadata=include_metadata,
        **kwargs,
    )


def on_serve(host: str = "0.0.0.0", port: int = 8772, **kwargs) -> None:
    return brain_hooks.on_serve(command_name="serve", host=host, port=port, **kwargs)
