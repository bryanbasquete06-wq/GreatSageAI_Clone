#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea Swarm — Multi-Agent Intelligence System
===================================================
Public API for the swarm of specialized AI agents.

Usage:
    from core.swarm import SwarmOrchestrator, ConsensusEngine

    swarm = SwarmOrchestrator(
        llm_engine=your_llm,
        on_progress=lambda p: print(p),
        on_log=lambda m: print(m),
    )

    result = swarm.run(
        goal="Create a REST API with auth, tests, and Docker",
    )
    print(result["output"])  # final refined code
"""

from core.swarm.models import (
    AgentRole, AgentMessage, AgentOpinion, MessageType,
    MessagePriority, AgentStatus, SwarmTask, SwarmState,
    ConsensusRound, ConsensusResult,
)
from core.swarm.agents import (
    SwarmAgent, ArchitectAgent, CoderAgent, ReviewerAgent,
    SecurityAgent, TesterAgent, ConductorAgent,
)
from core.swarm.orchestrator import SwarmOrchestrator, ConsensusEngine

__all__ = [
    "SwarmOrchestrator",
    "ConsensusEngine",
    "SwarmAgent",
    "ArchitectAgent",
    "CoderAgent",
    "ReviewerAgent",
    "SecurityAgent",
    "TesterAgent",
    "ConductorAgent",
    "AgentRole",
    "AgentMessage",
    "AgentOpinion",
    "MessageType",
    "MessagePriority",
    "AgentStatus",
    "SwarmTask",
    "SwarmState",
    "ConsensusRound",
    "ConsensusResult",
]
