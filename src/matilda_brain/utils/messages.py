"""Message building utilities for AI API requests."""

from typing import Any, Dict, List, Optional, Union, cast

from ..core.models import ImageInput


def build_message_list(
    prompt: Union[str, List[Union[str, ImageInput]]],
    system: Optional[str] = None,
    history: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Build a messages array for AI API requests.

    This utility consolidates the common pattern of building message lists
    for chat completion APIs. It handles system messages, conversation history,
    and multi-modal content (text + images).

    Args:
        prompt: The user prompt - can be a string or list of content (text/images)
        system: System prompt to prepend (optional)
        history: Previous conversation messages (optional)

    Returns:
        List of message dictionaries formatted for chat completion APIs

    Examples:
        >>> build_message_list("Hello")
        [{"role": "user", "content": "Hello"}]

        >>> build_message_list("Hi", system="Be helpful")
        [{"role": "system", "content": "Be helpful"}, {"role": "user", "content": "Hi"}]

        >>> build_message_list("Follow up", history=[{"role": "user", "content": "Hi"}])
        [{"role": "user", "content": "Hi"}, {"role": "user", "content": "Follow up"}]
    """
    messages: List[Dict[str, Any]] = []

    # Add system prompt if provided
    if system:
        messages.append({"role": "system", "content": system})

    # Add conversation history if provided
    if history:
        messages.extend(history)

    # Handle the current prompt
    if isinstance(prompt, str):
        messages.append({"role": "user", "content": prompt})
    else:
        # Build content array for multi-modal input
        content: List[Dict[str, Any]] = []
        for item in prompt:
            if isinstance(item, str):
                content.append({"type": "text", "text": item})
            elif isinstance(item, ImageInput):
                # Format image for the provider
                if item.is_url:
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": str(item.source)},
                        }
                    )
                else:
                    # Base64 encode for non-URL images
                    base64_data = item.to_base64()
                    mime_type = item.get_mime_type()
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{base64_data}"},
                        }
                    )
        messages.append({"role": "user", "content": content})

    return messages


def extract_messages_from_kwargs(kwargs: Optional[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """
    Extract pre-built messages from kwargs if present.

    This utility checks for pre-built messages that may be passed through
    from chat sessions or other sources.

    Args:
        kwargs: Dictionary that may contain a 'messages' key

    Returns:
        The pre-built messages list if present and non-empty, None otherwise
    """
    if kwargs and "messages" in kwargs and kwargs["messages"]:
        return cast(List[Dict[str, Any]], kwargs["messages"])
    return None
