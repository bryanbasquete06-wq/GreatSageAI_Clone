#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea Swarm — Specialized Agents
======================================
Each agent has a unique role, personality, and expertise.
They communicate via messages, debate solutions, and build consensus.
"""

from __future__ import annotations

import json
import re
import logging
from typing import Any, Dict, List, Optional

from core.swarm.models import (
    AgentRole, AgentMessage, AgentOpinion, MessageType,
    MessagePriority, AgentStatus, SwarmTask,
)

logger = logging.getLogger("elvea.swarm.agents")


# ═══════════════════════════════════════════════════════════════════════════════
# Base Agent
# ═══════════════════════════════════════════════════════════════════════════════

class SwarmAgent:
    """Base class for all swarm agents."""

    def __init__(self, role: AgentRole, llm_engine=None):
        self.role = role
        self._llm = llm_engine
        self.status = AgentStatus.IDLE
        self.inbox: List[AgentMessage] = []
        self.outbox: List[AgentMessage] = []
        self.knowledge: Dict[str, Any] = {}  # accumulated knowledge

    def set_llm(self, llm_engine):
        self._llm = llm_engine

    def receive(self, message: AgentMessage):
        """Receive a message from another agent."""
        self.inbox.append(message)
        if message.priority == MessagePriority.URGENT:
            self.status = AgentStatus.WORKING

    def send(self, receiver: AgentRole, msg_type: MessageType,
             content: str, priority: MessagePriority = MessagePriority.NORMAL,
             metadata: Dict = None, reply_to: str = None) -> AgentMessage:
        """Create and queue an outgoing message."""
        msg = AgentMessage(
            sender=self.role, receiver=receiver,
            msg_type=msg_type, priority=priority,
            content=content, metadata=metadata or {},
            reply_to=reply_to,
        )
        self.outbox.append(msg)
        return msg

    def broadcast(self, msg_type: MessageType, content: str,
                  priority: MessagePriority = MessagePriority.NORMAL,
                  metadata: Dict = None) -> AgentMessage:
        """Send a message to all agents (via conductor)."""
        return self.send(AgentRole.CONDUCTOR, msg_type, content, priority, metadata)

    def get_pending_messages(self) -> List[AgentMessage]:
        """Get and clear pending outgoing messages."""
        msgs = list(self.outbox)
        self.outbox.clear()
        return msgs

    def think(self, prompt: str, system: str = "") -> Optional[str]:
        """Use the LLM to think/generate a response."""
        if not self._llm:
            return None
        try:
            if hasattr(self._llm, 'chat'):
                resp = self._llm.chat(
                    [{"role": "user", "content": prompt}],
                    system=system or self._system_prompt(),
                    max_tokens=4096,
                )
                if resp.success:
                    return resp.text
            elif hasattr(self._llm, 'query'):
                return self._llm.query(prompt)
        except Exception as e:
            logger.error(f"{self.role.value} thinking failed: {e}")
        return None

    def _system_prompt(self) -> str:
        return f"You are a {self.role.value} agent in a software engineering swarm."

    def process_messages(self) -> List[AgentMessage]:
        """Process incoming messages and generate responses."""
        responses = []
        for msg in self.inbox:
            response = self._handle_message(msg)
            if response:
                responses.append(response)
        self.inbox.clear()
        return responses

    def _handle_message(self, msg: AgentMessage) -> Optional[AgentMessage]:
        """Override in subclasses to handle specific message types."""
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Architect Agent
# ═══════════════════════════════════════════════════════════════════════════════

class ArchitectAgent(SwarmAgent):
    """Designs system architecture, makes high-level structural decisions."""

    def __init__(self, llm_engine=None):
        super().__init__(AgentRole.ARCHITECT, llm_engine)

    def _system_prompt(self) -> str:
        return (
            "You are a Senior Software Architect in an AI engineering swarm.\n"
            "Your job: design system architecture, define project structure, "
            "make technology choices, and create the technical blueprint.\n\n"
            "You think in terms of: scalability, maintainability, separation of concerns, "
            "design patterns, and trade-offs. You are opinionated but data-driven.\n\n"
            "Always respond with structured JSON when asked to design."
        )

    def design_architecture(self, goal: str, context: str = "") -> Optional[str]:
        """Design the architecture for a goal."""
        self.status = AgentStatus.WORKING
        prompt = (
            f"Design the complete architecture for:\n\nGOAL: {goal}\n\n"
            f"CONTEXT: {context or 'New project'}\n\n"
            "Provide:\n"
            "1. Project structure (files and directories)\n"
            "2. Technology choices with justification\n"
            "3. Module responsibilities\n"
            "4. Data flow between components\n"
            "5. Key interfaces/contracts\n\n"
            "Respond in JSON format:\n"
            '{"structure": {"path": "description"}, '
            '"technologies": {"name": "reason"}, '
            '"modules": [{"name": "responsibility"}], '
            '"data_flow": "description", '
            '"key_decisions": ["decision: rationale"]}'
        )
        result = self.think(prompt)
        self.status = AgentStatus.IDLE
        return result

    def _handle_message(self, msg: AgentMessage) -> Optional[AgentMessage]:
        if msg.msg_type == MessageType.TASK_ASSIGN:
            design = self.design_architecture(msg.content, msg.metadata.get("context", ""))
            return self.send(
                AgentRole.CONDUCTOR, MessageType.TASK_RESULT,
                design or "Could not generate architecture",
                metadata={"step": "architecture", "agent": self.role.value},
            )
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Coder Agent
# ═══════════════════════════════════════════════════════════════════════════════

class CoderAgent(SwarmAgent):
    """Writes implementation code based on architecture and specs."""

    def __init__(self, llm_engine=None):
        super().__init__(AgentRole.CODER, llm_engine)

    def _system_prompt(self) -> str:
        return (
            "You are an Expert Programmer in an AI engineering swarm.\n"
            "Your job: write clean, production-ready code based on architecture specs.\n\n"
            "You follow: SOLID, DRY, KISS, YAGNI. You write complete code — no placeholders.\n"
            "You include error handling, type hints, and docstrings.\n"
            "You always consider edge cases and security.\n"
        )

    def write_code(self, spec: str, language: str = "python",
                   architecture: str = "") -> Optional[str]:
        """Generate code for a specification."""
        self.status = AgentStatus.WORKING
        prompt = (
            f"Write complete, production-ready {language} code for:\n\n"
            f"SPECIFICATION: {spec}\n\n"
            f"ARCHITECTURE CONTEXT:\n{architecture}\n\n"
            "Requirements:\n"
            "- Complete, runnable code (NO placeholders or TODOs)\n"
            "- Include error handling and type hints\n"
            "- Follow best practices for the language\n"
            "- Include a brief docstring\n"
            "Return ONLY the code, no explanations."
        )
        result = self.think(prompt)
        self.status = AgentStatus.IDLE
        return result

    def fix_code(self, code: str, error: str, language: str = "python") -> Optional[str]:
        """Fix code that has an error."""
        self.status = AgentStatus.WORKING
        prompt = (
            f"Fix this {language} code that has an error:\n\n"
            f"CODE:\n```{language}\n{code}\n```\n\n"
            f"ERROR:\n{error}\n\n"
            "Return the COMPLETE fixed code. No explanations."
        )
        result = self.think(prompt)
        self.status = AgentStatus.IDLE
        return result

    def _handle_message(self, msg: AgentMessage) -> Optional[AgentMessage]:
        if msg.msg_type == MessageType.TASK_ASSIGN:
            lang = msg.metadata.get("language", "python")
            arch = msg.metadata.get("architecture", "")
            code = self.write_code(msg.content, lang, arch)
            return self.send(
                AgentRole.CONDUCTOR, MessageType.TASK_RESULT,
                code or "Could not generate code",
                metadata={"step": "coding", "agent": self.role.value, "language": lang},
            )
        elif msg.msg_type == MessageType.FEEDBACK and "error" in msg.content.lower():
            code = msg.metadata.get("code", "")
            if code:
                fixed = self.fix_code(code, msg.content)
                if fixed:
                    msg.metadata["fixed_code"] = fixed
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Reviewer Agent
# ═══════════════════════════════════════════════════════════════════════════════

class ReviewerAgent(SwarmAgent):
    """Reviews code quality, suggests improvements, catches issues."""

    def __init__(self, llm_engine=None):
        super().__init__(AgentRole.REVIEWER, llm_engine)

    def _system_prompt(self) -> str:
        return (
            "You are a Senior Code Reviewer in an AI engineering swarm.\n"
            "Your job: review code for quality, correctness, and best practices.\n\n"
            "You are CRITICAL but CONSTRUCTIVE. You catch bugs, anti-patterns, "
            "security issues, and performance problems.\n"
            "You always provide specific improvement suggestions.\n\n"
            "Always respond with structured review in JSON format:\n"
            '{"verdict": "approve|reject|suggest_change", '
            '"issues": [{"severity": "critical|warning|info", "description": "...", "fix": "..."}], '
            '"suggestions": ["improvement suggestion"], '
            '"score": 0-100, '
            '"summary": "overall assessment"}'
        )

    def review_code(self, code: str, spec: str = "",
                    language: str = "python") -> Optional[str]:
        """Review code and provide structured feedback."""
        self.status = AgentStatus.WORKING
        prompt = (
            f"Review this {language} code critically:\n\n"
            f"```{language}\n{code}\n```\n\n"
            f"Original specification: {spec}\n\n"
            "Analyze for:\n"
            "1. Correctness — does it do what's needed?\n"
            "2. Error handling — are edge cases covered?\n"
            "3. Security — any vulnerabilities?\n"
            "4. Performance — any bottlenecks?\n"
            "5. Readability — is it clean and maintainable?\n"
            "6. Best practices — SOLID, DRY, etc.\n\n"
            "Be specific. Give line-level feedback where possible."
        )
        result = self.think(prompt)
        self.status = AgentStatus.IDLE
        return result

    def _handle_message(self, msg: AgentMessage) -> Optional[AgentMessage]:
        if msg.msg_type == MessageType.TASK_RESULT:
            code = msg.content
            spec = msg.metadata.get("spec", "")
            review = self.review_code(code, spec)
            return self.send(
                AgentRole.CONDUCTOR, MessageType.CODE_REVIEW,
                review or "Could not complete review",
                metadata={"step": "review", "agent": self.role.value},
            )
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Security Agent
# ═══════════════════════════════════════════════════════════════════════════════

class SecurityAgent(SwarmAgent):
    """Analyzes code for security vulnerabilities and hardens it."""

    def __init__(self, llm_engine=None):
        super().__init__(AgentRole.SECURITY, llm_engine)

    def _system_prompt(self) -> str:
        return (
            "You are a Security Engineer in an AI engineering swarm.\n"
            "Your job: find and fix security vulnerabilities in code.\n\n"
            "You check for: OWASP Top 10, injection attacks, authentication flaws, "
            "data exposure, insecure dependencies, hardcoded secrets, XSS, CSRF, "
            "SQL injection, command injection, path traversal, and more.\n\n"
            "Always respond in JSON:\n"
            '{"risk_level": "low|medium|high|critical", '
            '"vulnerabilities": [{"type": "...", "severity": "...", "location": "...", '
            '"description": "...", "fix": "..."}], '
            '"hardened_code": "complete fixed code if issues found", '
            '"summary": "security assessment"}'
        )

    def audit(self, code: str, language: str = "python") -> Optional[str]:
        """Perform security audit on code."""
        self.status = AgentStatus.WORKING
        prompt = (
            f"Perform a security audit on this {language} code:\n\n"
            f"```{language}\n{code}\n```\n\n"
            "Check for:\n"
            "1. Injection vulnerabilities (SQL, command, code)\n"
            "2. Authentication/authorization flaws\n"
            "3. Data exposure (secrets, PII, tokens)\n"
            "4. Input validation gaps\n"
            "5. Dependency vulnerabilities\n"
            "6. Insecure configurations\n\n"
            "If vulnerabilities found, provide the COMPLETE hardened code."
        )
        result = self.think(prompt)
        self.status = AgentStatus.IDLE
        return result

    def _handle_message(self, msg: AgentMessage) -> Optional[AgentMessage]:
        if msg.msg_type == MessageType.TASK_RESULT:
            audit = self.audit(msg.content, msg.metadata.get("language", "python"))
            return self.send(
                AgentRole.CONDUCTOR, MessageType.SECURITY_AUDIT,
                audit or "Could not complete audit",
                metadata={"step": "security", "agent": self.role.value},
            )
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Tester Agent
# ═══════════════════════════════════════════════════════════════════════════════

class TesterAgent(SwarmAgent):
    """Generates and runs tests for code validation."""

    def __init__(self, llm_engine=None):
        super().__init__(AgentRole.TESTER, llm_engine)

    def _system_prompt(self) -> str:
        return (
            "You are a QA Engineer in an AI engineering swarm.\n"
            "Your job: write comprehensive tests that catch bugs.\n\n"
            "You write: unit tests, integration tests, edge case tests, "
            "error handling tests, and boundary condition tests.\n"
            "You use pytest conventions. You test both happy paths and error cases.\n"
        )

    def generate_tests(self, code: str, language: str = "python",
                       test_framework: str = "pytest") -> Optional[str]:
        """Generate comprehensive tests for code."""
        self.status = AgentStatus.WORKING
        prompt = (
            f"Write comprehensive {test_framework} tests for this code:\n\n"
            f"```{language}\n{code}\n```\n\n"
            "Include:\n"
            "1. Happy path tests\n"
            "2. Edge case tests\n"
            "3. Error handling tests\n"
            "4. Boundary condition tests\n"
            "5. At least 80% code coverage\n\n"
            "Write COMPLETE test code — no placeholders."
        )
        result = self.think(prompt)
        self.status = AgentStatus.IDLE
        return result

    def _handle_message(self, msg: AgentMessage) -> Optional[AgentMessage]:
        if msg.msg_type == MessageType.TASK_RESULT:
            tests = self.generate_tests(
                msg.content, msg.metadata.get("language", "python")
            )
            return self.send(
                AgentRole.CONDUCTOR, MessageType.TEST_RESULT,
                tests or "Could not generate tests",
                metadata={"step": "testing", "agent": self.role.value},
            )
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Conductor Agent
# ═══════════════════════════════════════════════════════════════════════════════

class ConductorAgent(SwarmAgent):
    """Orchestrates the swarm, routes messages, resolves conflicts."""

    def __init__(self, llm_engine=None):
        super().__init__(AgentRole.CONDUCTOR, llm_engine)
        self.agents: Dict[AgentRole, SwarmAgent] = {}
        self.task_queue: List[SwarmTask] = []

    def register_agent(self, agent: SwarmAgent):
        """Register a specialized agent with the conductor."""
        self.agents[agent.role] = agent

    def dispatch(self, task: SwarmTask):
        """Dispatch a task to the appropriate agents."""
        self.task_queue.append(task)
        for role in task.assigned_to:
            if role in self.agents:
                msg = AgentMessage(
                    sender=self.role, receiver=role,
                    msg_type=MessageType.TASK_ASSIGN,
                    priority=task.priority,
                    content=task.description,
                    metadata=task.context,
                )
                self.agents[role].receive(msg)

    def collect_responses(self) -> List[AgentMessage]:
        """Collect all responses from agents."""
        responses = []
        for role, agent in self.agents.items():
            if role == AgentRole.CONDUCTOR:
                continue
            agent.status = AgentStatus.WORKING
            agent_responses = agent.process_messages()
            responses.extend(agent_responses)
            agent.get_pending_messages()  # clear outbox
        return responses

    def route_message(self, message: AgentMessage):
        """Route a message to the correct agent."""
        target = message.receiver
        if target == AgentRole.CONDUCTOR:
            self.inbox.append(message)
        elif target in self.agents:
            self.agents[target].receive(message)

    def broadcast_to_all(self, msg_type: MessageType, content: str,
                         metadata: Dict = None):
        """Broadcast a message to all registered agents."""
        for role, agent in self.agents.items():
            if role == AgentRole.CONDUCTOR:
                continue
            msg = AgentMessage(
                sender=self.role, receiver=role,
                msg_type=msg_type, content=content,
                metadata=metadata or {},
            )
            agent.receive(msg)

    def _system_prompt(self) -> str:
        return (
            "You are the Conductor of an AI engineering swarm.\n"
            "Your job: coordinate specialized agents, resolve conflicts, "
            "and make final decisions.\n\n"
            "You are decisive, fair, and quality-focused.\n"
            "When agents disagree, you evaluate both sides and choose the best path.\n"
        )
