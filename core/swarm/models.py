#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea Swarm — Data Models
===============================
All data structures for the multi-agent swarm intelligence system.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentRole(Enum):
    """Specialized roles in the swarm."""
    CONDUCTOR = "conductor"     # Orchestrates the swarm
    ARCHITECT = "architect"     # Designs structure & architecture
    CODER = "coder"             # Writes implementation code
    REVIEWER = "reviewer"       # Reviews & critiques code
    SECURITY = "security"       # Security analysis & hardening
    TESTER = "tester"           # Test generation & validation


class MessageType(Enum):
    """Types of inter-agent messages."""
    TASK_ASSIGN = "task_assign"
    TASK_RESULT = "task_result"
    CODE_REVIEW = "code_review"
    SECURITY_AUDIT = "security_audit"
    TEST_RESULT = "test_result"
    DEBATE_CHALLENGE = "debate_challenge"
    DEBATE_DEFENSE = "debate_defense"
    CONSENSUS_VOTE = "consensus_vote"
    CONSENSUS_FINAL = "consensus_final"
    STATUS_UPDATE = "status_update"
    ESCALATION = "escalation"
    FEEDBACK = "feedback"


class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class AgentStatus(Enum):
    IDLE = "idle"
    WORKING = "working"
    DEBATING = "debating"
    WAITING = "waiting"
    ERROR = "error"
    OFFLINE = "offline"


class ConsensusResult(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REVISED = "revised"
    ESCALATED = "escalated"


@dataclass
class AgentMessage:
    """A message between swarm agents."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    sender: AgentRole = AgentRole.CONDUCTOR
    receiver: AgentRole = AgentRole.CONDUCTOR  # or BROADCAST
    msg_type: MessageType = MessageType.STATUS_UPDATE
    priority: MessagePriority = MessagePriority.NORMAL
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    reply_to: Optional[str] = None  # message ID this replies to
    requires_response: bool = False

    BROADCAST: AgentRole = AgentRole.CONDUCTOR  # sentinel for broadcast


@dataclass
class AgentOpinion:
    """An agent's opinion on a proposed solution."""
    agent: AgentRole
    verdict: str  # "approve", "reject", "suggest_change"
    confidence: float = 0.5  # 0.0 - 1.0
    reasoning: str = ""
    suggestions: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConsensusRound:
    """A single round of consensus voting."""
    round_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    topic: str = ""
    proposal: str = ""
    opinions: List[AgentOpinion] = field(default_factory=list)
    result: Optional[ConsensusResult] = None
    final_decision: str = ""
    timestamp: float = field(default_factory=time.time)

    @property
    def approve_count(self) -> int:
        return sum(1 for o in self.opinions if o.verdict == "approve")

    @property
    def reject_count(self) -> int:
        return sum(1 for o in self.opinions if o.verdict == "reject")

    @property
    def total_opinions(self) -> int:
        return len(self.opinions)

    @property
    def consensus_reached(self) -> bool:
        if not self.opinions:
            return False
        return self.approve_count > len(self.opinions) / 2

    @property
    def avg_confidence(self) -> float:
        if not self.opinions:
            return 0.0
        return sum(o.confidence for o in self.opinions) / len(self.opinions)


@dataclass
class SwarmTask:
    """A task assigned to the swarm."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    description: str = ""
    assigned_to: List[AgentRole] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    @property
    def elapsed(self) -> float:
        end = self.completed_at or time.time()
        return end - self.created_at


@dataclass
class SwarmState:
    """Complete state of the swarm."""
    phase: str = "idle"  # idle, planning, executing, debating, done
    task: Optional[SwarmTask] = None
    messages: List[AgentMessage] = field(default_factory=list)
    consensus_rounds: List[ConsensusRound] = field(default_factory=list)
    agent_status: Dict[str, AgentStatus] = field(default_factory=dict)
    final_output: Optional[str] = None
    start_time: float = 0.0
    total_tokens: int = 0

    def __post_init__(self):
        if not self.agent_status:
            self.agent_status = {r.value: AgentStatus.IDLE for r in AgentRole}

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time if self.start_time else 0

    @property
    def consensus_count(self) -> int:
        return len(self.consensus_rounds)

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def get_messages_for(self, role: AgentRole) -> List[AgentMessage]:
        return [m for m in self.messages if m.receiver == role or m.receiver == AgentRole.CONDUCTOR]
