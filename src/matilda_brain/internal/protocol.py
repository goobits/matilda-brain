from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import json

PROTOCOL_VERSION = "v1"


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class RiskLevel(str, Enum):
    """The risk level associated with a proposal."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Proposal(BaseModel):
    """A request from an Agent to perform a sensitive action."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tool_name: str
    action_name: str
    params: Dict[str, Any]
    risk_level: RiskLevel = RiskLevel.MEDIUM
    reasoning: str


class ContentKind(str, Enum):
    TEXT = "text"
    PROPOSAL = "proposal"
    HANDOFF = "handoff"
    ERROR = "error"


class Message(BaseModel):
    """
    The atomic unit of communication in the Switchboard.
    Matches Rust struct:
    struct Message {
        role: Role,
        #[serde(flatten)]
        content: Content, // Content is tagged with "kind"
        metadata: HashMap<String, String>
    }

    JSON Output:
    {
        "role": "user",
        "kind": "text",
        "text": "Hello",
        "metadata": {}
    }
    """

    role: Role
    kind: ContentKind
    metadata: Dict[str, str] = Field(default_factory=dict)

    # Fields for Content::Text
    text: Optional[str] = None

    # Fields for Content::Proposal
    proposal: Optional[Proposal] = None

    # Fields for Content::Handoff
    target_agent: Optional[str] = None
    reason: Optional[str] = None
    context: Dict[str, str] = Field(default_factory=dict)

    # Fields for Content::Error
    code: Optional[str] = None
    message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    @classmethod
    def user(cls, text: str) -> "Message":
        return cls(role=Role.USER, kind=ContentKind.TEXT, text=text)

    @classmethod
    def assistant(cls, text: str) -> "Message":
        return cls(role=Role.ASSISTANT, kind=ContentKind.TEXT, text=text)

    @classmethod
    def system(cls, text: str) -> "Message":
        return cls(role=Role.SYSTEM, kind=ContentKind.TEXT, text=text)

    @classmethod
    def proposal_msg(cls, proposal: Proposal, role: Role = Role.ASSISTANT) -> "Message":
        return cls(role=role, kind=ContentKind.PROPOSAL, proposal=proposal)

    def to_protocol_json(self) -> str:
        """Serializes to JSON matching the Rust ProtocolEnvelope."""
        # We need to manually construct the dict to ensure correct structure
        # because Pydantic's exclude_none=True might hide fields we want,
        # or include fields we don't (like all the optional ones).

        base = {
            "version": PROTOCOL_VERSION,
            "role": self.role.value,
            "kind": self.kind.value,
            "metadata": self.metadata,
        }

        if self.kind == ContentKind.TEXT:
            base["text"] = self.text

        elif self.kind == ContentKind.PROPOSAL:
            if self.proposal:
                prop_data = json.loads(self.proposal.model_dump_json())
                base["proposal"] = prop_data
                # Wait, Rust enum Content::Proposal(Proposal)
                # If tagged="kind", it is { "kind": "proposal", "proposal_field1": ... }?
                # OR { "kind": "proposal", "proposal": { ... } }?
                #
                # In Rust: Proposal(Proposal) -> Tuple Variant.
                # serde(tag="kind") for tuple variant implies:
                # { "kind": "proposal", "proposal_field_1": val, ... } IF flattened?
                # No, standard tuple variant with tag usually expects:
                # { "kind": "proposal", "field1": ... } if it's a struct variant.
                # Since Proposal is a struct, `Proposal(Proposal)` is a NewType Variant.
                # Serde treats NewType variants with internal tags by flattening the newtype's content.
                # So: { "kind": "proposal", "id": "...", "tool_name": "..." }
                #
                # So we must flatten 'proposal' fields into 'base'.
                base.update(prop_data)

        elif self.kind == ContentKind.HANDOFF:
            base["target_agent"] = self.target_agent
            base["reason"] = self.reason
            base["context"] = self.context

        elif self.kind == ContentKind.ERROR:
            base["code"] = self.code
            base["message"] = self.message
            if self.details:
                base["details"] = self.details

        return json.dumps(base)
