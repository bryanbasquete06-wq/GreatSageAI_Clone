#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elivea Agent — Plan Generator
=================================
Generates multiple candidate execution plans for a given goal,
evaluates them, and selects the best one based on strategy.
"""

from __future__ import annotations

import json
import re
import time
import logging
from typing import Any, Dict, List, Optional, Tuple

from core.agent.models import (
    Plan, PlanStep, PlanStrategy, StepAction, DecisionPoint,
)

logger = logging.getLogger("elvea.agent.planner")


# ═══════════════════════════════════════════════════════════════════════════════
# Plan Generation Prompts
# ═══════════════════════════════════════════════════════════════════════════════

_PLANNING_PROMPT = """You are an expert software architect. Given a goal, create a detailed execution plan.

GOAL: {goal}

STRATEGY: {strategy}
{strategy_desc}

EXISTING PROJECT CONTEXT:
{context}

RULES:
1. Break the goal into concrete, atomic steps (max 20 steps)
2. Each step must be independently testable
3. Order steps by dependency (earlier steps don't depend on later ones)
4. Assign action types: create_file, modify_file, run_command, run_tests, install_deps, create_dir, write_config
5. Include estimated seconds per step
6. For each step, provide the EXACT file path and content/command

RESPOND IN THIS JSON FORMAT:
{{
  "analysis": "Brief analysis of the goal and approach",
  "steps": [
    {{
      "id": 1,
      "description": "Clear description of what this step does",
      "action": "create_file|modify_file|run_command|run_tests|install_deps|create_dir|write_config",
      "params": {{
        "path": "relative/file/path.py",
        "content": "file content or command to run",
        "language": "python|javascript|bash|sql|docker|yaml",
        "purpose": "why this step exists"
      }},
      "dependencies": [],
      "estimated_seconds": 30,
      "confidence": 0.9
    }}
  ],
  "tradeoffs": {{
    "speed": "description of speed considerations",
    "quality": "description of quality considerations",
    "scalability": "description of scalability considerations"
  }},
  "total_estimated_seconds": 300
}}

IMPORTANT:
- Make steps CONCRETE — real file paths, real code, real commands
- Not vague descriptions like "create backend" — instead "create main.py with FastAPI app, /health endpoint, SQLAlchemy User model"
- Each step should produce something testable
- If the goal involves multiple files, create separate steps for each
"""

_REPLAN_PROMPT = """The current execution plan has failed. Analyze the failure and generate a revised plan.

ORIGINAL GOAL: {goal}
FAILED STEP: Step {failed_id} — {failed_desc}
ERROR: {error}
ERROR CATEGORY: {error_category}

WHAT WAS ALREADY COMPLETED:
{completed_steps}

WHAT STILL NEEDS TO BE DONE:
{remaining_steps}

LESSONS FROM PREVIOUS ATTEMPTS:
{lessons}

Generate a REVISED plan that:
1. Fixes whatever caused the failure
2. Reuses completed work where possible
3. Avoids the patterns that caused the error
4. May restructure remaining steps if needed

Use the same JSON format as before.
"""


class PlanGenerator:
    """Generates and evaluates execution plans using LLM."""

    def __init__(self, llm_engine=None):
        self._llm = llm_engine
        self._plans_cache: Dict[str, List[Plan]] = {}

    def set_llm(self, llm_engine):
        self._llm = llm_engine

    def generate_plans(
        self,
        goal: str,
        context: str = "",
        strategy: PlanStrategy = PlanStrategy.BALANCED,
        num_plans: int = 3,
    ) -> List[Plan]:
        """Generate multiple candidate plans for a goal."""
        logger.info(f"Generating {num_plans} plans for: {goal[:80]}...")

        strategy_descs = {
            PlanStrategy.SPEED: "Prioritize speed. Minimal tests, simple architecture, get it working fast.",
            PlanStrategy.QUALITY: "Prioritize quality. Full tests, clean architecture, documentation, error handling.",
            PlanStrategy.BALANCED: "Good balance between speed and quality. Reasonable tests, clean code.",
            PlanStrategy.LEARNING: "Prioritize learning. Extra comments, step-by-step explanations, educational code.",
        }

        plans = []
        strategies_to_try = [strategy]
        # Add alternative strategies for variety
        if strategy != PlanStrategy.QUALITY:
            strategies_to_try.append(PlanStrategy.QUALITY)
        if strategy != PlanStrategy.SPEED:
            strategies_to_try.append(PlanStrategy.SPEED)

        for i, strat in enumerate(strategies_to_try[:num_plans]):
            try:
                plan = self._generate_single_plan(
                    goal, context, strat, strategy_descs.get(strat, "")
                )
                if plan and plan.steps:
                    plans.append(plan)
            except Exception as e:
                logger.warning(f"Plan generation failed for {strat.value}: {e}")

        # Score and sort
        for plan in plans:
            plan.score = self._score_plan(plan, strategy)

        plans.sort(key=lambda p: p.score, reverse=True)
        logger.info(f"Generated {len(plans)} plans, best score: {plans[0].score:.2f}" if plans else "No plans generated")
        return plans

    def generate_replan(
        self,
        goal: str,
        failed_plan: Plan,
        error: str,
        error_category: str,
        lessons: List[str] = None,
    ) -> Optional[Plan]:
        """Generate a revised plan after a failure."""
        logger.info(f"Replanning after failure in step {failed_plan.current_step_index}")

        completed = []
        remaining = []
        for step in failed_plan.steps:
            if step.status.value == "completed":
                completed.append(f"  Step {step.id}: {step.description} ✓")
            elif step.status.value == "skipped":
                completed.append(f"  Step {step.id}: {step.description} (skipped)")
            else:
                remaining.append(f"  Step {step.id}: {step.description}")

        failed_step = failed_plan.get_failed_steps()
        failed_info = failed_step[0] if failed_step else failed_plan.steps[0]

        prompt = _REPLAN_PROMPT.format(
            goal=goal,
            failed_id=failed_info.id,
            failed_desc=failed_info.description,
            error=error[:500],
            error_category=error_category,
            completed_steps="\n".join(completed) if completed else "  (none)",
            remaining_steps="\n".join(remaining) if remaining else "  (none)",
            lessons="\n".join(f"  - {l}" for l in (lessons or [])) or "  (none)",
        )

        return self._call_llm_plan(prompt)

    def select_best_plan(
        self,
        plans: List[Plan],
        strategy: PlanStrategy = PlanStrategy.BALANCED,
    ) -> Optional[Plan]:
        """Select the best plan, optionally with user collaboration."""
        if not plans:
            return None
        for plan in plans:
            plan.score = self._score_plan(plan, strategy)
        plans.sort(key=lambda p: p.score, reverse=True)
        return plans[0]

    def create_decision_point(
        self,
        plans: List[Plan],
    ) -> DecisionPoint:
        """Create a decision point for user to choose between plans."""
        options = []
        for i, plan in enumerate(plan_map := plans):
            label = f"Plano {chr(65+i)}: {plan.strategy.value}"
            desc = f"{plan.total_steps} passos, ~{plan.estimated_seconds}s"
            if plan.tradeoffs:
                desc += f" | {list(plan.tradeoffs.values())[0][:60]}"
            options.append({"label": label, "description": desc})

        return DecisionPoint(
            question="Escolha qual plano executar:",
            options=options,
            context=f"Objetivo: {plans[0].goal[:100] if plans else '?'}",
            recommended=0,
        )

    # ── Internal Methods ──────────────────────────────────────────────

    def _generate_single_plan(
        self, goal: str, context: str, strategy: PlanStrategy, strategy_desc: str
    ) -> Optional[Plan]:
        """Generate a single plan via LLM."""
        prompt = _PLANNING_PROMPT.format(
            goal=goal,
            strategy=strategy.value,
            strategy_desc=strategy_desc,
            context=context or "(new project, no existing context)",
        )

        response_text = self._call_llm(prompt)
        if not response_text:
            return None

        return self._parse_plan_response(response_text, goal, strategy)

    def _call_llm(self, prompt: str) -> Optional[str]:
        """Call the LLM engine for plan generation."""
        if not self._llm:
            logger.error("No LLM engine configured for plan generation")
            return None

        try:
            messages = [{"role": "user", "content": prompt}]
            system = (
                "You are an expert software architect and project planner. "
                "Always respond with valid JSON. Be extremely specific and concrete "
                "in your plans — real file paths, real code, real commands. "
                "Never be vague."
            )

            if hasattr(self._llm, 'chat'):
                response = self._llm.chat(messages, system=system, max_tokens=8192)
                if response.success:
                    return response.text
            elif hasattr(self._llm, 'query'):
                return self._llm.query(prompt)

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
        return None

    def _parse_plan_response(
        self, text: str, goal: str, strategy: PlanStrategy
    ) -> Optional[Plan]:
        """Parse LLM response into a Plan object."""
        # Extract JSON from response (may be wrapped in markdown)
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        json_str = json_match.group(1) if json_match else text

        # Try to find JSON object
        start = json_str.find('{')
        end = json_str.rfind('}')
        if start >= 0 and end > start:
            json_str = json_str[start:end + 1]

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse plan JSON: {e}")
            # Try to extract steps from partial JSON
            return self._fallback_parse(text, goal, strategy)

        steps = []
        for s in data.get("steps", []):
            try:
                action_str = s.get("action", "custom")
                try:
                    action = StepAction(action_str)
                except ValueError:
                    action = StepAction.CUSTOM

                step = PlanStep(
                    id=s.get("id", len(steps) + 1),
                    description=s.get("description", ""),
                    action=action,
                    params=s.get("params", {}),
                    dependencies=s.get("dependencies", []),
                    confidence=s.get("confidence", 0.8),
                )
                steps.append(step)
            except Exception as e:
                logger.debug(f"Skipping malformed step: {e}")

        if not steps:
            return None

        return Plan(
            goal=goal,
            description=data.get("analysis", ""),
            steps=steps,
            strategy=strategy,
            estimated_seconds=data.get("total_estimated_seconds", sum(
                30 for _ in steps
            )),
            tradeoffs=data.get("tradeoffs", {}),
        )

    def _fallback_parse(self, text: str, goal: str, strategy: PlanStrategy) -> Optional[Plan]:
        """Fallback parser when JSON fails — extract steps from natural language."""
        # Look for numbered lists
        step_pattern = re.compile(
            r'(?:^|\n)\s*(?:\d+[\.\)]\s*|\-\s*|Step\s+\d+:\s*)(.+)',
            re.MULTILINE
        )
        matches = step_pattern.findall(text)
        if not matches:
            return None

        steps = []
        for i, desc in enumerate(matches, 1):
            desc = desc.strip().rstrip('*#')
            if len(desc) < 5:
                continue
            # Guess action type from description
            action = self._guess_action(desc)
            steps.append(PlanStep(
                id=i,
                description=desc,
                action=action,
                confidence=0.6,
            ))

        return Plan(
            goal=goal,
            description=text[:200],
            steps=steps,
            strategy=strategy,
            estimated_seconds=len(steps) * 30,
        ) if steps else None

    @staticmethod
    def _guess_action(description: str) -> StepAction:
        """Guess step action type from description text."""
        d = description.lower()
        # Order matters: more specific patterns first
        if any(k in d for k in ("test", "verify", "validate", "check", "pytest", "unittest")):
            return StepAction.RUN_TESTS
        if any(k in d for k in ("install", "pip install", "npm install", "dependency", "dependencies")):
            return StepAction.INSTALL_DEPS
        if any(k in d for k in ("create", "new file", "write file", "add file")):
            return StepAction.CREATE_FILE
        if any(k in d for k in ("modify", "update", "edit", "change file")):
            return StepAction.MODIFY_FILE
        if any(k in d for k in ("run command", "execute", "build", "compile", "run script")):
            return StepAction.RUN_COMMAND
        if any(k in d for k in ("directory", "folder", "mkdir")):
            return StepAction.CREATE_DIR
        if any(k in d for k in ("config", "configure", "setup", "settings")):
            return StepAction.WRITE_CONFIG
        return StepAction.CUSTOM

    @staticmethod
    def _score_plan(plan: Plan, target_strategy: PlanStrategy) -> float:
        """Score a plan from 0-100 based on multiple factors."""
        if not plan.steps:
            return 0.0

        score = 50.0  # base

        # Strategy alignment bonus
        if plan.strategy == target_strategy:
            score += 15

        # Step quality
        avg_confidence = sum(s.confidence for s in plan.steps) / len(plan.steps)
        score += avg_confidence * 10

        # Step count penalty (too few = incomplete, too many = over-engineered)
        n = len(plan.steps)
        if n < 3:
            score -= 10  # too simple
        elif n > 15:
            score -= 5   # over-engineered
        elif 5 <= n <= 10:
            score += 5   # sweet spot

        # Has concrete code in params
        concrete_steps = sum(
            1 for s in plan.steps
            if s.params.get("content") or s.params.get("command")
        )
        score += (concrete_steps / max(n, 1)) * 10

        # Has tests
        has_tests = any(s.action == StepAction.RUN_TESTS for s in plan.steps)
        if has_tests:
            score += 5
        if target_strategy == PlanStrategy.QUALITY and not has_tests:
            score -= 10

        # Time estimate reasonableness
        if plan.estimated_seconds < 60:
            score -= 5  # too optimistic
        elif plan.estimated_seconds > 3600:
            score -= 5  # too pessimistic

        # Trade-offs documented
        if plan.tradeoffs:
            score += 3

        return max(0.0, min(100.0, score))
