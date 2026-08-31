#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea Swarm — Orchestrator
================================
Manages the full swarm lifecycle: agent coordination, parallel execution,
debate resolution, consensus building, and final output synthesis.
"""

from __future__ import annotations

import json
import time
import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from core.swarm.models import (
    AgentRole, AgentMessage, AgentOpinion, MessageType,
    MessagePriority, AgentStatus, SwarmTask, SwarmState,
    ConsensusRound, ConsensusResult,
)
from core.swarm.agents import (
    SwarmAgent, ArchitectAgent, CoderAgent, ReviewerAgent,
    SecurityAgent, TesterAgent, ConductorAgent,
)

logger = logging.getLogger("elvea.swarm.orchestrator")


# ═══════════════════════════════════════════════════════════════════════════════
# Consensus Engine
# ═══════════════════════════════════════════════════════════════════════════════

class ConsensusEngine:
    """Builds consensus from multiple agent opinions."""

    def __init__(self, min_approvals: int = 0, confidence_threshold: float = 0.6):
        # 0 = majority
        self.min_approvals = min_approvals
        self.confidence_threshold = confidence_threshold

    def evaluate(self, opinions: List[AgentOpinion], topic: str = "",
                 proposal: str = "") -> ConsensusRound:
        """Evaluate opinions and reach consensus."""
        round = ConsensusRound(topic=topic, proposal=proposal, opinions=opinions)

        if not opinions:
            round.result = ConsensusResult.REJECTED
            round.final_decision = "No opinions received"
            return round

        avg_conf = sum(o.confidence for o in opinions) / len(opinions)
        approve = sum(1 for o in opinions if o.verdict == "approve")
        reject = sum(1 for o in opinions if o.verdict == "reject")
        suggest = sum(1 for o in opinions if o.verdict == "suggest_change")
        total = len(opinions)

        min_needed = self.min_approvals if self.min_approvals > 0 else total // 2 + 1

        # Collect all suggestions
        all_suggestions = []
        for o in opinions:
            all_suggestions.extend(o.suggestions)

        if approve >= min_needed and avg_conf >= self.confidence_threshold:
            round.result = ConsensusResult.ACCEPTED
            round.final_decision = f"Approved by {approve}/{total} agents (confidence: {avg_conf:.0%})"
        elif reject >= min_needed:
            round.result = ConsensusResult.REJECTED
            round.final_decision = f"Rejected by {reject}/{total} agents"
        elif suggest > 0 and approve >= reject:
            round.result = ConsensusResult.REVISED
            round.final_decision = f"Revised with {len(all_suggestions)} suggestions"
        else:
            round.result = ConsensusResult.ESCALATED
            round.final_decision = f"Mixed opinions — escalated to conductor"

        return round

    def merge_suggestions(self, opinions: List[AgentOpinion]) -> List[str]:
        """Merge and deduplicate suggestions from multiple agents."""
        seen = set()
        merged = []
        for o in sorted(opinions, key=lambda x: x.confidence, reverse=True):
            for s in o.suggestions:
                s_lower = s.lower().strip()
                if s_lower not in seen:
                    seen.add(s_lower)
                    merged.append(s)
        return merged


# ═══════════════════════════════════════════════════════════════════════════════
# Swarm Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

class SwarmOrchestrator:
    """
    Manages the complete swarm lifecycle:

    1. ASSEMBLE  — create and register all specialized agents
    2. PLAN      — Architect designs the solution
    3. CODE      — Coder implements it
    4. REVIEW    — Reviewer + Security + Tester analyze in parallel
    5. DEBATE    — If disagreements, agents debate
    6. CONSENSUS — Vote on final approach
    7. REFINE    — Iterate based on feedback
    8. DELIVER   — Final output
    """

    def __init__(
        self,
        llm_engine=None,
        on_progress: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
    ):
        self._llm = llm_engine
        self._on_progress = on_progress
        self._on_log = on_log

        # Create all agents
        self.conductor = ConductorAgent(llm_engine)
        self.architect = ArchitectAgent(llm_engine)
        self.coder = CoderAgent(llm_engine)
        self.reviewer = ReviewerAgent(llm_engine)
        self.security = SecurityAgent(llm_engine)
        self.tester = TesterAgent(llm_engine)
        self.consensus = ConsensusEngine()

        # Register with conductor
        for agent in [self.architect, self.coder, self.reviewer,
                      self.security, self.tester]:
            self.conductor.register_agent(agent)

        # State
        self._state = SwarmState()
        self._max_debate_rounds = 3
        self._max_iterations = 5

    def set_llm(self, llm_engine):
        """Update LLM engine for all agents."""
        self._llm = llm_engine
        for agent in [self.conductor, self.architect, self.coder,
                      self.reviewer, self.security, self.tester]:
            agent.set_llm(llm_engine)

    @property
    def state(self) -> SwarmState:
        return self._state

    @property
    def progress(self) -> Dict[str, Any]:
        return {
            "phase": self._state.phase,
            "messages": self._state.message_count,
            "consensus_rounds": self._state.consensus_count,
            "elapsed": self._state.elapsed,
            "agents": {r.value: s.value for r, s in
                       ((ar, self._get_agent_status(ar)) for ar in AgentRole)},
        }

    # ═══════════════════════════════════════════════════════════════════
    # MAIN SWARM LOOP
    # ═══════════════════════════════════════════════════════════════════

    def run(self, goal: str, context: str = "") -> Dict[str, Any]:
        """
        Run the full swarm pipeline on a goal.
        Returns the final output and metrics.
        """
        self._state = SwarmState(start_time=time.time())
        self._log(f"🐝 Swarm activated: {goal[:80]}")

        try:
            # Phase 1: ARCHITECTURE
            self._set_phase("planning")
            architecture = self._phase_architecture(goal, context)
            if not architecture:
                return self._result(success=False, error="Architecture generation failed")

            # Phase 2: CODE GENERATION
            self._set_phase("executing")
            code = self._phase_coding(goal, architecture)
            if not code:
                return self._result(success=False, error="Code generation failed")

            # Phase 3: PARALLEL REVIEW
            self._set_phase("reviewing")
            reviews = self._phase_review(code, goal)

            # Phase 4: DEBATE & CONSENSUS
            self._set_phase("debating")
            final_code = self._phase_debate_and_refine(code, goal, architecture, reviews)

            # Phase 5: TESTING
            self._set_phase("testing")
            tests = self._phase_testing(final_code)

            # Phase 6: DELIVER
            self._set_phase("done")
            self._state.final_output = final_code
            self._log("✅ Swarm completed successfully")

            return self._result(
                success=True,
                output=final_code,
                metadata={
                    "architecture": architecture,
                    "tests": tests,
                    "iterations": self._state.consensus_count,
                },
            )

        except Exception as e:
            self._set_phase("failed")
            logger.error(f"Swarm crashed: {e}", exc_info=True)
            return self._result(success=False, error=str(e))

    # ═══════════════════════════════════════════════════════════════════
    # PHASES
    # ═══════════════════════════════════════════════════════════════════

    def _phase_architecture(self, goal: str, context: str) -> Optional[str]:
        """Phase 1: Architect designs the solution."""
        self._log("🏗️ Architect designing architecture...")
        design = self.architect.design_architecture(goal, context)
        if design:
            self._log("📐 Architecture designed")
            # Broadcast architecture to all agents
            self.conductor.broadcast_to_all(
                MessageType.STATUS_UPDATE,
                f"Architecture ready: {design[:200]}",
                {"architecture": design, "goal": goal},
            )
        return design

    def _phase_coding(self, goal: str, architecture: str) -> Optional[str]:
        """Phase 2: Coder implements the solution."""
        self._log("💻 Coder writing implementation...")
        code = self.coder.write_code(goal, architecture=architecture)
        if code:
            self._log(f"📝 Code generated ({len(code)} chars)")
        return code

    def _phase_review(self, code: str, goal: str) -> Dict[str, Any]:
        """Phase 3: Reviewer, Security, and Tester analyze in parallel."""
        self._log("🔍 Running parallel reviews...")

        results = {}

        # Reviewer
        self._log("  📋 Reviewer analyzing code quality...")
        review = self.reviewer.review_code(code, goal)
        results["review"] = review

        # Security
        self._log("  🔒 Security auditing...")
        security = self.security.audit(code)
        results["security"] = security

        # Tester
        self._log("  🧪 Tester generating tests...")
        tests = self.tester.generate_tests(code)
        results["tests"] = tests

        self._log("📊 All reviews complete")
        return results

    def _phase_debate_and_refine(
        self, code: str, goal: str, architecture: str,
        reviews: Dict[str, Any]
    ) -> str:
        """Phase 4: Agents debate and refine the solution."""
        current_code = code

        for iteration in range(self._max_iterations):
            # Collect opinions from all reviewers
            opinions = self._collect_opinions(current_code, goal, reviews)

            # Build consensus
            round = self.consensus.evaluate(
                opinions,
                topic=f"Iteration {iteration + 1}: Code quality",
                proposal=current_code[:500],
            )
            self._state.consensus_rounds.append(round)

            self._log(
                f"🗳️ Consensus round {iteration + 1}: "
                f"{round.result.value if round.result else '?'} "
                f"({round.approve_count}/{round.total_opinions} approve)"
            )

            # Check if accepted
            if round.result == ConsensusResult.ACCEPTED:
                self._log("✅ Consensus reached — code accepted")
                break

            # If rejected or needs revision, fix the code
            if round.result in (ConsensusResult.REJECTED, ConsensusResult.REVISED):
                suggestions = self.consensus.merge_suggestions(opinions)
                self._log(f"🔧 Applying {len(suggestions)} suggestions...")
                fixed = self._apply_suggestions(
                    current_code, suggestions, goal, architecture
                )
                if fixed:
                    current_code = fixed
                else:
                    break  # Can't fix, accept as-is

            # Escalated — conductor makes final call
            if round.result == ConsensusResult.ESCALATED:
                self._log("⚖️ Conductor resolving conflict...")
                resolved = self._conductor_resolve(
                    current_code, opinions, goal
                )
                if resolved:
                    current_code = resolved
                break

        return current_code

    def _phase_testing(self, code: str) -> Optional[str]:
        """Phase 5: Generate and validate tests."""
        self._log("🧪 Generating comprehensive tests...")
        tests = self.tester.generate_tests(code)
        if tests:
            self._log(f"📝 Tests generated ({len(tests)} chars)")
        return tests

    # ═══════════════════════════════════════════════════════════════════
    # DEBATE & CONSENSUS HELPERS
    # ═══════════════════════════════════════════════════════════════════

    def _collect_opinions(self, code: str, goal: str,
                          reviews: Dict[str, Any]) -> List[AgentOpinion]:
        """Collect opinions from all review agents."""
        opinions = []

        # Parse reviewer feedback
        review_text = reviews.get("review", "")
        opinions.append(self._parse_opinion(
            AgentRole.REVIEWER, review_text, code
        ))

        # Parse security feedback
        sec_text = reviews.get("security", "")
        opinions.append(self._parse_opinion(
            AgentRole.SECURITY, sec_text, code
        ))

        # Parse test feedback
        test_text = reviews.get("tests", "")
        if test_text:
            opinions.append(AgentOpinion(
                agent=AgentRole.TESTER,
                verdict="approve" if len(test_text) > 100 else "suggest_change",
                confidence=0.7 if len(test_text) > 100 else 0.5,
                reasoning="Tests generated" if test_text else "No tests generated",
            ))

        return [o for o in opinions if o is not None]

    def _parse_opinion(self, role: AgentRole, review_text: str,
                       code: str) -> Optional[AgentOpinion]:
        """Parse an agent's review text into a structured opinion."""
        if not review_text:
            return AgentOpinion(
                agent=role, verdict="approve",
                confidence=0.5, reasoning="No review available",
            )

        text_lower = review_text.lower()

        # Try to extract JSON verdict
        try:
            json_match = re.search(r'\{[^{}]*"verdict"[^{}]*\}', review_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return AgentOpinion(
                    agent=role,
                    verdict=data.get("verdict", "approve"),
                    confidence=data.get("score", 70) / 100,
                    reasoning=data.get("summary", ""),
                    suggestions=data.get("suggestions", []),
                )
        except Exception:
            pass

        # Fallback: heuristic parsing
        if any(k in text_lower for k in ("critical", "reject", "vulnerability", "dangerous")):
            verdict = "reject"
            conf = 0.8
        elif any(k in text_lower for k in ("suggest", "improve", "could be better", "recommend")):
            verdict = "suggest_change"
            conf = 0.7
        else:
            verdict = "approve"
            conf = 0.75

        suggestions = []
        for line in review_text.split("\n"):
            line = line.strip()
            if line.startswith("- ") or line.startswith("• "):
                suggestions.append(line[2:])

        return AgentOpinion(
            agent=role, verdict=verdict, confidence=conf,
            reasoning=review_text[:300],
            suggestions=suggestions[:5],
        )

    def _apply_suggestions(self, code: str, suggestions: List[str],
                           goal: str, architecture: str) -> Optional[str]:
        """Apply suggestions to improve code."""
        if not suggestions:
            return code

        prompt = (
            f"Improve this code based on review suggestions:\n\n"
            f"CODE:\n```python\n{code}\n```\n\n"
            f"SUGGESTIONS TO APPLY:\n"
            + "\n".join(f"- {s}" for s in suggestions[:10])
            + f"\n\nGOAL: {goal}\n"
            "Return the COMPLETE improved code. No explanations."
        )
        return self.coder.think(prompt)

    def _conductor_resolve(self, code: str, opinions: List[AgentOpinion],
                           goal: str) -> Optional[str]:
        """Conductor makes final decision when consensus fails."""
        opinions_text = "\n".join(
            f"- {o.agent.value}: {o.verdict} ({o.confidence:.0%}) — {o.reasoning[:100]}"
            for o in opinions
        )
        prompt = (
            f"The swarm could not reach consensus on this code.\n\n"
            f"CODE:\n```python\n{code[:2000]}\n```\n\n"
            f"AGENT OPINIONS:\n{opinions_text}\n\n"
            f"GOAL: {goal}\n\n"
            "As the Conductor, make a final decision:\n"
            "1. Evaluate both sides\n"
            "2. Choose the best path forward\n"
            "3. If the code needs changes, provide the COMPLETE improved version\n"
            "4. If the code is acceptable as-is, return it unchanged\n\n"
            "Return the final code (complete, no placeholders)."
        )
        return self.conductor.think(prompt)

    # ═══════════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════════

    def _set_phase(self, phase: str):
        self._state.phase = phase
        self._emit_progress()

    def _get_agent_status(self, role: AgentRole) -> AgentStatus:
        agents = {
            AgentRole.CONDUCTOR: self.conductor,
            AgentRole.ARCHITECT: self.architect,
            AgentRole.CODER: self.coder,
            AgentRole.REVIEWER: self.reviewer,
            AgentRole.SECURITY: self.security,
            AgentRole.TESTER: self.tester,
        }
        agent = agents.get(role)
        return agent.status if agent else AgentStatus.OFFLINE

    def _emit_progress(self):
        if self._on_progress:
            try:
                self._on_progress(self.progress)
            except Exception:
                pass

    def _log(self, message: str):
        logger.info(message)
        if self._on_log:
            try:
                self._on_log(message)
            except Exception:
                pass

    def _result(self, success: bool = True, output: str = "",
                error: str = "", metadata: Dict = None) -> Dict[str, Any]:
        return {
            "success": success,
            "output": output,
            "error": error,
            "elapsed": round(self._state.elapsed, 2),
            "consensus_rounds": self._state.consensus_count,
            "messages": self._state.message_count,
            "phase": self._state.phase,
            **(metadata or {}),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get full swarm status."""
        return {
            "phase": self._state.phase,
            "progress": self.progress,
            "consensus_rounds": [
                {"topic": r.topic, "result": r.result.value if r.result else "?",
                 "opinions": r.total_opinions}
                for r in self._state.consensus_rounds
            ],
            "agents": {
                role.value: {
                    "status": self._get_agent_status(role).value,
                    "inbox_size": len(agent.inbox),
                }
                for role, agent in [
                    (AgentRole.ARCHITECT, self.architect),
                    (AgentRole.CODER, self.coder),
                    (AgentRole.REVIEWER, self.reviewer),
                    (AgentRole.SECURITY, self.security),
                    (AgentRole.TESTER, self.tester),
                ]
            },
        }


# Needed for _parse_opinion
import re
