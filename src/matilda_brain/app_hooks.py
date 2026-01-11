"""Hook implementations for Matilda Brain - Text to Text."""

from typing import Optional, Tuple

from matilda_brain.internal import hooks as internal_hooks


def on_ask(
    prompt: Optional[Tuple[str, ...]] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tools: Optional[bool] = None,
    session: Optional[str] = None,
    system: Optional[str] = None,
    stream: Optional[bool] = None,
    json: bool = False,
    **kwargs,
) -> None:
    internal_hooks.on_ask(
        command_name="ask",
        prompt=prompt or (),
        model=model,
        temperature=temperature if temperature is not None else 0.7,
        max_tokens=max_tokens,
        tools=bool(tools),
        session=session,
        system=system,
        stream=bool(stream),
        json=bool(json),
        **kwargs,
    )


def on_chat(
    model: Optional[str] = None,
    session: Optional[str] = None,
    tools: Optional[bool] = None,
    markdown: Optional[bool] = None,
    **kwargs,
) -> None:
    internal_hooks.on_chat(
        command_name="chat",
        model=model,
        session=session,
        tools=bool(tools),
        markdown=markdown,
        **kwargs,
    )


def on_stateless(
    message: Optional[Tuple[str, ...]] = None,
    system: Optional[str] = None,
    history: Optional[str] = None,
    tools: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **kwargs,
) -> None:
    internal_hooks.on_stateless(
        command_name="stateless",
        message=message or (),
        system=system,
        history=history,
        tools=tools,
        model=model,
        temperature=temperature if temperature is not None else 0.7,
        max_tokens=max_tokens if max_tokens is not None else 2048,
        **kwargs,
    )


def on_list(format: Optional[str] = None, **kwargs) -> None:
    if "show_secrets" in kwargs:
        internal_hooks.on_config_list(command_name="config", show_secrets=bool(kwargs["show_secrets"]))
        return

    if "show_disabled" in kwargs:
        internal_hooks.on_tools_list(command_name="tools", show_disabled=bool(kwargs["show_disabled"]))
        return

    resource = kwargs.pop("resource", None)
    internal_hooks.on_list(
        command_name="list",
        resource=resource,
        format=format or "table",
        **kwargs,
    )


def on_status(json: bool = False, **kwargs) -> None:
    internal_hooks.on_status(command_name="status", json=bool(json), **kwargs)


def on_models(json: bool = False, **kwargs) -> None:
    internal_hooks.on_models(command_name="models", json=bool(json), **kwargs)


def on_info(model: Optional[str] = None, json: bool = False, **kwargs) -> None:
    internal_hooks.on_info(command_name="info", model=model, json=bool(json), **kwargs)


def on_export(
    session: Optional[str] = None,
    format: Optional[str] = None,
    output: Optional[str] = None,
    include_metadata: Optional[bool] = None,
    **kwargs,
) -> None:
    internal_hooks.on_export(
        command_name="export",
        session=session,
        format=format or "markdown",
        output=output,
        include_metadata=bool(include_metadata),
        **kwargs,
    )


def on_get(key: str, **kwargs) -> None:
    internal_hooks.on_config_get(command_name="config", key=key, **kwargs)


def on_set(key: str, value: str, **kwargs) -> None:
    internal_hooks.on_config_set(command_name="config", key=key, value=value, **kwargs)


def on_enable(tool_name: str, **kwargs) -> None:
    internal_hooks.on_tools_enable(command_name="tools", tool_name=tool_name, **kwargs)


def on_disable(tool_name: str, **kwargs) -> None:
    internal_hooks.on_tools_disable(command_name="tools", tool_name=tool_name, **kwargs)


def on_serve(host: Optional[str] = None, port: Optional[int] = None, **kwargs) -> None:
    internal_hooks.on_serve(command_name="serve", host=host or "0.0.0.0", port=port or 8772, **kwargs)
