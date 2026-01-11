"""Enhanced chat functionality with persistence support."""

import asyncio
import json
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional, Union

from ..backends import BaseBackend
from ..core.exceptions import InvalidParameterError, SessionLoadError, SessionSaveError
from ..core.models import AIResponse, ImageInput
from ..core.routing import router
from ..internal.utils import get_logger, run_async
from ..memory_client import get_memory, MemoryStore
from .serialization import (
    deserialize_tools,
    estimate_tokens,
    export_messages_json,
    export_messages_markdown,
    export_messages_text,
    serialize_tools,
)

logger = get_logger(__name__)


# Re-export for backwards compatibility
_estimate_tokens = estimate_tokens


class PersistentChatSession:
    """
    Chat session with conversation memory and persistence support.

    This enhanced session supports:
    - Saving and loading conversation history
    - Metadata tracking (timestamps, model usage, costs)
    - Multiple persistence formats (JSON, pickle)
    - Session resumption
    - Tool persistence and execution
    - Git-backed long-term memory via matilda-memory
    """

    def __init__(
        self,
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        backend: Optional[Union[str, BaseBackend]] = None,
        session_id: Optional[str] = None,
        tools: Optional[List] = None,
        **kwargs: Any,
    ):
        """
        Initialize a chat session.

        Args:
            system: System prompt to set the assistant's behavior
            model: Default model to use for this session
            backend: Backend to use for this session
            session_id: Unique identifier for this session
            tools: List of functions/tools the AI can call
            **kwargs: Additional parameters passed to each request
        """
        self.system = system
        self.model = model
        self.kwargs = kwargs
        self.tools = tools
        self.history: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {
            "session_id": session_id or self._generate_session_id(),
            "created_at": datetime.now().isoformat(),
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "total_cost": 0.0,
            "model_usage": {},
            "backend_usage": {},
            "tools_used": {},
        }
        
        # Initialize memory client
        memory_enabled = kwargs.get("memory_enabled", True)
        self.agent_name = kwargs.get("agent_name", "assistant")
        self.memory = get_memory(memory_enabled, agent_name=self.agent_name)

        # Resolve backend using router
        if backend is None:
            self.backend, resolved_model = router.smart_route(
                "placeholder",
                model=model,
                **kwargs,  # Just for backend selection
            )
            # Use user-specified model if provided, otherwise use resolved
            self.model = model if model is not None else resolved_model
        else:
            self.backend = router.resolve_backend(backend)
            if model is None:
                self.model = router.resolve_model(None, self.backend)
            else:
                self.model = model

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        import uuid

        return f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    @property
    def session_id(self) -> str:
        """Get the session ID."""
        return str(self.metadata["session_id"])

    @property
    def messages(self) -> List[Dict[str, Any]]:
        """Get the message history (alias for history)."""
        return self.history

    def ask(
        self,
        prompt: Union[str, List[Union[str, ImageInput]]],
        *,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> AIResponse:
        """
        Ask a question in this chat session.

        Args:
            prompt: Your message - can be text or multi-modal content
            model: Override the session's default model
            **kwargs: Additional parameters for this request

        Returns:
            AIResponse with the assistant's reply
        """
        # Record timestamp
        timestamp = datetime.now().isoformat()
        
        # Helper to extract text from prompt
        user_text = ""
        if isinstance(prompt, str):
            user_text = prompt
        elif isinstance(prompt, list):
            for item in prompt:
                if isinstance(item, str):
                    user_text += item + " "
        
        # Query memory for context
        memory_context = ""
        if user_text:
            try:
                results = self.memory.query(self.agent_name, user_text.strip(), limit=3)
                if results:
                    context_items = [f"[{r.type}:{r.path}]\n{r.content[:500]}" for r in results]
                    memory_context = "\n\nRelevant knowledge:\n" + "\n---\n".join(context_items)
            except Exception as e:
                logger.debug(f"Memory query failed: {e}")

        # Add user message to history
        self.history.append({"role": "user", "content": prompt, "timestamp": timestamp})

        # Track multimodal usage
        if isinstance(prompt, list):
            # Count images in the prompt
            image_count = sum(1 for item in prompt if isinstance(item, ImageInput))
            if image_count > 0:
                if "multimodal_messages" not in self.metadata:
                    self.metadata["multimodal_messages"] = 0
                if "total_images" not in self.metadata:
                    self.metadata["total_images"] = 0
                self.metadata["multimodal_messages"] += 1
                self.metadata["total_images"] += image_count

        # Build messages for API
        messages = []
        
        # Inject system prompt with memory context
        system_content = self.system or ""
        if memory_context:
            if system_content:
                system_content += "\n\n" + memory_context
            else:
                system_content = "You are a helpful AI assistant.\n\n" + memory_context
        
        if system_content:
            messages.append({"role": "system", "content": system_content})

        for msg in self.history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # For backends that don't support message format, convert to string
        if hasattr(self.backend, "supports_messages") and not self.backend.supports_messages:
            # Convert to conversation format
            conversation = self._messages_to_conversation(messages)
            full_prompt: Union[str, List[Union[str, ImageInput]]] = conversation
        else:
            # Use last message as prompt (backend will handle history)
            full_prompt = prompt

        # Merge parameters
        params = {**self.kwargs, **kwargs}

        # Make the request
        async def _ask_wrapper() -> AIResponse:
            return await self.backend.ask(
                full_prompt,
                model=model or self.model,
                system=system_content if len(self.history) == 1 else None,
                messages=(messages if hasattr(self.backend, "supports_messages") else None),
                tools=self.tools,
                **params,
            )

        response = run_async(_ask_wrapper())

        # Add assistant response to history
        response_entry: Dict[str, Any] = {
            "role": "assistant",
            "content": str(response),
            "timestamp": datetime.now().isoformat(),
            "model": response.model,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "cost": response.cost,
        }

        # Add tool call information if tools were called
        if hasattr(response, "tools_called") and response.tools_called:
            response_entry["tools_called"] = True
            response_entry["tool_calls"] = [
                {
                    "id": call.id,
                    "name": call.name,
                    "arguments": call.arguments,
                    "result": call.result,
                    "succeeded": call.succeeded,
                    "error": call.error,
                }
                for call in response.tool_calls
            ]

            # Update tools usage metadata
            for call in response.tool_calls:
                if call.name not in self.metadata["tools_used"]:
                    self.metadata["tools_used"][call.name] = 0
                self.metadata["tools_used"][call.name] += 1

        self.history.append(response_entry)

        # Update metadata
        self._update_metadata(response)
        
        # Log to long-term memory
        try:
            self.memory.log_conversation(self.agent_name, [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": str(response)}
            ])
            # Auto-learning
            run_async(self._extract_and_store_knowledge(user_text, str(response)))
        except Exception as e:
            logger.debug(f"Memory logging failed: {e}")

        return response

    async def _extract_and_store_knowledge(self, user_input: str, response: str) -> None:
        """Extract facts and store in memory."""
        # Check for learning trigger words to avoid LLM call overhead on every turn
        # Heuristic: only learn if user talks about themselves or preferences
        triggers = ["my", "i like", "i prefer", "i don't", "remember", "keep in mind", "always", "never"]
        if not any(t in user_input.lower() for t in triggers):
            return

        prompt = f"""Extract permanent facts about the user or project from this exchange.
Return ONLY the facts as markdown bullet points. If nothing worth remembering, return empty string.

User: {user_input}
Assistant: {response}"""

        try:
            # We use a cheaper/faster model if possible, or same model
            # For now reuse self.backend
            extraction = await self.backend.ask(
                prompt,
                model=self.model,
                system="You are a knowledge extraction system. Extract facts concisely.",
                temperature=0.0
            )
            
            facts = str(extraction).strip()
            if facts and "no facts" not in facts.lower():
                # Generate a slug
                import re
                slug = re.sub(r'[^a-z0-9]+', '-', user_input[:30].lower()).strip('-')
                if not slug:
                    slug = "general"
                
                path = f"facts/{datetime.now().strftime('%Y%m%d')}-{slug}.md"
                self.memory.add_knowledge(
                    self.agent_name, 
                    path, 
                    f"# Learned Facts\n\nSource: Conversation\nDate: {datetime.now().isoformat()}\n\n{facts}",
                    commit_message=f"Learned facts about {slug}"
                )
        except Exception as e:
            logger.debug(f"Knowledge extraction failed: {e}")

    def stream(
        self,
        prompt: Union[str, List[Union[str, ImageInput]]],
        *,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """
        Stream a response in this chat session.

        Args:
            prompt: Your message - can be text or multi-modal content
            model: Override the session's default model
            **kwargs: Additional parameters for this request

        Yields:
            String chunks as they arrive
        """
        # Record timestamp
        timestamp = datetime.now().isoformat()

        # Add user message to history
        self.history.append({"role": "user", "content": prompt, "timestamp": timestamp})

        # Build messages for API
        messages = []
        if self.system:
            messages.append({"role": "system", "content": self.system})

        for msg in self.history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Prepare prompt
        if hasattr(self.backend, "supports_messages") and not self.backend.supports_messages:
            conversation = self._messages_to_conversation(messages)
            full_prompt: Union[str, List[Union[str, ImageInput]]] = conversation
        else:
            full_prompt = prompt

        # Merge parameters
        params = {**self.kwargs, **kwargs}

        # Collect response for history
        response_chunks = []

        # Stream the response
        async def _async_stream() -> AsyncIterator[str]:
            async for chunk in self.backend.astream(
                full_prompt,
                model=model or self.model,
                system=self.system if len(self.history) == 1 else None,
                messages=(messages if hasattr(self.backend, "supports_messages") else None),
                tools=self.tools,
                **params,
            ):
                response_chunks.append(chunk)
                yield chunk

        # Run async generator in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async_gen = _async_stream()
            while True:
                try:
                    chunk = loop.run_until_complete(async_gen.__anext__())
                    yield chunk
                except StopAsyncIteration:
                    break
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        # Add complete response to history
        full_response = "".join(response_chunks)
        self.history.append(
            {
                "role": "assistant",
                "content": full_response,
                "timestamp": datetime.now().isoformat(),
                "model": model or self.model,
            }
        )

    def clear(self) -> None:
        """Clear conversation history while preserving session metadata."""
        self.history.clear()
        # Reset message count
        self.metadata["message_count"] = 0
        logger.debug(f"Cleared history for session {self.metadata['session_id']}")

    def save(self, path: Union[str, Path], format: str = "json") -> Path:
        """
        Save the chat session to disk.

        Args:
            path: File path to save to
            format: Save format - only "json" is supported (pickle removed for security)

        Returns:
            Path where the session was saved
        """
        path = Path(path)

        # Warn if pickle format requested (deprecated for security)
        if format == "pickle":
            warnings.warn(
                "Pickle format is deprecated due to security concerns. Using JSON instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            format = "json"
            # Change extension if needed
            if path.suffix in [".pkl", ".pickle"]:
                path = path.with_suffix(".json")

        if format != "json":
            raise InvalidParameterError("format", format, "Only 'json' format is supported")

        # Update metadata with current message count
        self.metadata["message_count"] = len(self.history)

        # Prepare session data
        # Handle backend name extraction safely
        backend_name = None
        if hasattr(self.backend, "name") and isinstance(self.backend.name, str):
            backend_name = self.backend.name
        elif hasattr(self.backend, "__class__"):
            backend_name = self.backend.__class__.__name__
        else:
            backend_name = str(type(self.backend).__name__)

        session_data = {
            "version": "1.0",
            "session_id": self.metadata.get("session_id"),
            "system": self.system,
            "model": self.model,
            "backend": backend_name,
            "tools": self._serialize_tools() if self.tools else None,
            "messages": self.history,  # Use 'messages' for compatibility
            "history": self.history,  # Keep 'history' for backward compatibility
            "metadata": self.metadata,
            "kwargs": self.kwargs,
        }

        try:
            # JSON format - human readable and secure
            with open(path, "w") as f:
                json.dump(session_data, f, indent=2, default=str)
            logger.info(f"Saved session to {path} (JSON format)")
        except PermissionError as e:
            raise SessionSaveError(str(path), f"Permission denied: {e}") from e
        except OSError as e:
            raise SessionSaveError(str(path), f"OS error: {e}") from e
        except (TypeError, ValueError) as e:
            raise SessionSaveError(str(path), f"JSON serialization error: {e}") from e
        except Exception as e:
            raise SessionSaveError(str(path), str(e)) from e

        return path

    @classmethod
    def load(cls, path: Union[str, Path], format: Optional[str] = None) -> "PersistentChatSession":
        """
        Load a chat session from disk.

        Args:
            path: File path to load from
            format: Load format - "json" preferred, "pickle" deprecated but supported for migration

        Returns:
            Loaded PersistentChatSession instance
        """
        path = Path(path)

        # Auto-detect format
        if format is None:
            if path.suffix == ".json":
                format = "json"
            elif path.suffix in [".pkl", ".pickle"]:
                format = "pickle"
            else:
                # Try JSON first
                format = "json"

        try:
            if format == "json":
                with open(path) as f:
                    session_data = json.load(f)
            else:
                # Pickle support removed for security
                if path.suffix in [".pkl", ".pickle"] or format == "pickle":
                    raise SessionLoadError(str(path), "Pickle format is no longer supported for security reasons.")

                # Default to JSON
                with open(path) as f:
                    session_data = json.load(f)
        except FileNotFoundError:
            raise SessionLoadError(str(path), "File not found") from None
        except json.JSONDecodeError as e:
            raise SessionLoadError(str(path), f"Invalid JSON: {e}") from e
        except Exception as e:
            raise SessionLoadError(str(path), str(e)) from e

        # Create new session
        # Support session_id from top level or metadata
        session_id = session_data.get("session_id") or session_data.get("metadata", {}).get("session_id")

        # Only pass backend if it's a valid backend name
        backend_name = session_data.get("backend")
        if backend_name and backend_name in ["MagicMock", "Mock", "AsyncMock", "mock"]:
            # Skip mock backends when loading
            backend_name = None

        session = cls(
            system=session_data.get("system"),
            model=session_data.get("model"),
            backend=backend_name,
            session_id=session_id,
            tools=(cls._deserialize_tools(session_data.get("tools")) if session_data.get("tools") else None),
            **session_data.get("kwargs", {}),
        )

        # Restore history and metadata
        # Support both 'messages' and 'history' for compatibility
        session.history = session_data.get("messages", session_data.get("history", []))
        session.metadata.update(session_data.get("metadata", {}))

        logger.info(f"Loaded session from {path} ({len(session.history)} messages)")
        return session

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the chat session.

        Returns:
            Dictionary with session statistics
        """
        # Calculate duration in minutes (precise with fractions)
        duration_str = self._calculate_duration()
        duration_minutes = self._calculate_duration_minutes()

        return {
            "session_id": self.metadata["session_id"],
            "created_at": self.metadata["created_at"],
            "message_count": len(self.history),
            "user_messages": len([m for m in self.history if m["role"] == "user"]),
            "assistant_messages": len([m for m in self.history if m["role"] == "assistant"]),
            "total_tokens_in": self.metadata["total_tokens_in"],
            "total_tokens_out": self.metadata["total_tokens_out"],
            "total_cost": self.metadata["total_cost"],
            "model_usage": self.metadata["model_usage"],
            "duration": duration_str,
            "duration_minutes": duration_minutes,
            "models_used": list(self.metadata.get("model_usage", {}).keys()),
            "backends_used": list(self.metadata.get("backend_usage", {}).keys()),
        }

    def export_messages(self, format: str = "text") -> str:
        """
        Export conversation messages in various formats.

        Args:
            format: Export format - "text", "markdown", or "json"

        Returns:
            Formatted conversation string
        """
        if format == "text":
            return export_messages_text(self.history)
        elif format == "markdown":
            return export_messages_markdown(
                self.history, session_id=self.metadata.get("session_id", "Unknown"), system=self.system
            )
        elif format == "json":
            return export_messages_json(
                self.history,
                session_id=self.metadata.get("session_id"),
                created_at=self.metadata.get("created_at"),
                system=self.system,
            )
        else:
            raise ValueError(f"Unknown format: {format}")

    def _messages_to_conversation(self, messages: List[Dict[str, Any]]) -> str:
        """Convert messages to conversation format for backends that need it."""
        conversation = []
        for msg in messages:
            if msg["role"] == "system":
                conversation.append(f"System: {msg['content']}")
            elif msg["role"] == "user":
                content = msg["content"]
                if isinstance(content, list):
                    # Extract text from multi-modal content
                    text_parts = [item for item in content if isinstance(item, str)]
                    content = " ".join(text_parts)
                conversation.append(f"Human: {content}")
            else:
                conversation.append(f"Assistant: {msg['content']}")
        return "\n\n".join(conversation)

    def _update_metadata(self, response: AIResponse) -> None:
        """Update session metadata with response information."""
        if response.tokens_in:
            self.metadata["total_tokens_in"] += response.tokens_in
        if response.tokens_out:
            self.metadata["total_tokens_out"] += response.tokens_out
        if response.cost:
            self.metadata["total_cost"] += response.cost

        # Track model usage
        model = response.model or self.model
        if model:
            if model not in self.metadata["model_usage"]:
                self.metadata["model_usage"][model] = {
                    "count": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cost": 0.0,
                }
            self.metadata["model_usage"][model]["count"] += 1
            if response.tokens_in:
                self.metadata["model_usage"][model]["tokens_in"] += response.tokens_in
            if response.tokens_out:
                self.metadata["model_usage"][model]["tokens_out"] += response.tokens_out
            if response.cost:
                self.metadata["model_usage"][model]["cost"] += response.cost

        # Track backend usage
        if response.backend:
            backend_name = response.backend
        elif hasattr(self.backend, "name") and isinstance(self.backend.name, str):
            backend_name = self.backend.name
        else:
            backend_name = str(type(self.backend).__name__)

        if backend_name:
            if backend_name not in self.metadata["backend_usage"]:
                self.metadata["backend_usage"][backend_name] = {
                    "count": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cost": 0.0,
                }
            self.metadata["backend_usage"][backend_name]["count"] += 1
            if response.tokens_in:
                self.metadata["backend_usage"][backend_name]["tokens_in"] += response.tokens_in
            if response.tokens_out:
                self.metadata["backend_usage"][backend_name]["tokens_out"] += response.tokens_out
            if response.cost:
                self.metadata["backend_usage"][backend_name]["cost"] += response.cost

    def _calculate_duration(self) -> str:
        """Calculate session duration."""
        if not self.history:
            return "0m"

        try:
            start = datetime.fromisoformat(self.metadata["created_at"])
            last_msg = self.history[-1]
            if "timestamp" in last_msg:
                end = datetime.fromisoformat(last_msg["timestamp"])
                duration = end - start

                total_seconds = int(duration.total_seconds())

                if duration.days > 0:
                    # Calculate hours and minutes within the current day
                    remaining_seconds = total_seconds % (24 * 3600)
                    hours = remaining_seconds // 3600
                    minutes = (remaining_seconds % 3600) // 60
                    return f"{duration.days}d {hours}h {minutes}m"
                else:
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    if hours > 0:
                        return f"{hours}h {minutes}m"
                    else:
                        return f"{minutes}m"
        except (ValueError, KeyError, AttributeError) as e:
            logger.debug(f"Could not calculate session duration: {e}")

        return "Unknown"

    def _calculate_duration_minutes(self) -> float:
        """Calculate session duration in minutes (with fractions)."""
        if not self.history:
            return 0.0

        try:
            start = datetime.fromisoformat(self.metadata["created_at"])
            last_msg = self.history[-1]
            if "timestamp" in last_msg:
                end = datetime.fromisoformat(last_msg["timestamp"])
                duration = end - start
                return duration.total_seconds() / 60.0
        except (ValueError, KeyError, AttributeError) as e:
            logger.debug(f"Could not calculate session duration in minutes: {e}")

        return 0.0

    def _serialize_tools(self) -> List[Dict[str, Any]]:
        """Serialize tools for storage."""
        return serialize_tools(self.tools)

    @staticmethod
    def _deserialize_tools(serialized_tools: List[Dict[str, Any]]) -> List:
        """Deserialize tools from storage."""
        return deserialize_tools(serialized_tools)
