"""Agent controller with EGATS planner, lifecycle management, and session persistence."""

from __future__ import annotations

import asyncio
import logging
import re
from enum import Enum
from typing import Any, ClassVar

from excalibur.core.backend import (
    AgentBackend,
    AgentMessage,
    ClaudeCodeBackend,
    MessageType,
)
from excalibur.core.config import ExcaliburConfig
from excalibur.core.events import Event, EventBus, EventType
from excalibur.core.session import SessionStatus, SessionStore

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Simple 5-state model for agent lifecycle."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class AgentController:
    """Central orchestrator with EGATS planner and lifecycle management.

    Features:
    - TDA-EGATS planning loop (attack tree search)
    - Framework-agnostic via AgentBackend
    - Pause/resume/stop control
    - Instruction injection
    - Session persistence with attack tree state
    - Memory subsystem integration (state store + context assembly)
    """

    # Flag detection patterns
    FLAG_PATTERNS: ClassVar[list[str]] = [
        r"flag\{[^\}]+\}",  # flag{...}
        r"FLAG\{[^\}]+\}",  # FLAG{...}
        r"HTB\{[^\}]+\}",  # HTB{...}
        r"CTF\{[^\}]+\}",  # CTF{...}
        r"[A-Za-z0-9_]+\{[^\}]+\}",  # Generic CTF format
        r"\b[a-f0-9]{32}\b",  # 32-char hex (HTB user/root flags)
    ]

    # Prompt-driven success marker. Vulhub targets have no flags, so the
    # prompt is instructed to print this exact word when it has confirmed
    # exploitation; matched as a whole word so it won't false-positive on
    # things like "UNSUCCESSFUL". Change this if the prompt's wording changes.
    SUCCESS_MARKER: ClassVar[str] = "SUCCESS"

    def __init__(
        self,
        config: ExcaliburConfig,
        backend: AgentBackend | None = None,
        session_store: SessionStore | None = None,
        events: EventBus | None = None,
    ):
        """Initialize controller.

        Args:
            config: Excalibur configuration.
            backend: Optional custom backend (defaults to ClaudeCodeBackend).
            session_store: Optional custom session store.
            events: Optional custom event bus.
        """
        self.config = config
        self.backend = backend
        self.sessions = session_store or SessionStore()
        self.events = events or EventBus.get()

        # State management
        self._state = AgentState.IDLE
        self._pause_requested = False
        self._stop_requested = False
        self._success_detected = False
        self._resume_event = asyncio.Event()
        self._pending_instruction: str | None = None

        # EGATS components (lazy-initialized)
        self._planner: Any = None
        self._state_store: Any = None
        self._context_assembler: Any = None
        self._context_compressor: Any = None
        self._tool_registry: Any = None
        self._attack_tree: Any = None

        # Subscribe to user events
        self.events.subscribe(EventType.USER_COMMAND, self._on_user_command)
        self.events.subscribe(EventType.USER_INPUT, self._on_user_input)

    def _init_egats(self) -> None:
        """Lazy-initialize EGATS planner and memory components."""
        from excalibur.memory.context_assembler import ContextAssembler
        from excalibur.memory.context_compressor import ContextCompressor
        from excalibur.memory.state_store import StateStore
        from excalibur.planner.egats import EGATSPlanner
        from excalibur.tools.registry import get_registry

        self._planner = EGATSPlanner(config=self.config.egats_config)
        self._state_store = StateStore(db_path=self.config.state_store_path)
        self._context_assembler = ContextAssembler(self._state_store)
        self._context_compressor = ContextCompressor(
            ideal_threshold=self.config.context_ideal_threshold,
            aggressive_threshold=self.config.context_aggressive_threshold,
        )
        self._tool_registry = get_registry()

    @property
    def state(self) -> AgentState:
        """Get current agent state."""
        return self._state

    def _set_state(
        self,
        state: AgentState,
        details: str = "",
        target: str | None = None,
        task: str | None = None,
    ) -> None:
        """Update state and emit event."""
        self._state = state
        self.events.emit_state(state.value, details, target=target, task=task)

    # === Control Methods (called from TUI) ===

    def pause(self) -> bool:
        """Request pause at next safe point."""
        if self._state == AgentState.RUNNING:
            self._pause_requested = True
            return True
        return False

    def resume(self, instruction: str | None = None) -> bool:
        """Resume from paused state."""
        if self._state == AgentState.PAUSED:
            self._pending_instruction = instruction
            self._pause_requested = False
            self._resume_event.set()
            return True
        return False

    def stop(self) -> bool:
        """Request stop."""
        self._stop_requested = True
        self._resume_event.set()  # Unblock if paused
        return True

    def inject(self, instruction: str) -> bool:
        """Queue instruction for next pause point."""
        if self._state in (AgentState.RUNNING, AgentState.PAUSED):
            self._pending_instruction = instruction
            if self._state == AgentState.RUNNING:
                self._pause_requested = True
            return True
        return False

    # === Event Handlers ===

    def _on_user_command(self, event: Event) -> None:
        """Handle user command events."""
        cmd = event.data.get("command")
        if cmd == "pause":
            self.pause()
        elif cmd == "resume":
            self.resume()
        elif cmd == "stop":
            self.stop()

    def _on_user_input(self, event: Event) -> None:
        """Handle user input events."""
        text = event.data.get("text", "")
        if text:
            self.inject(text)

    # === Pause/Resume Check ===

    async def _check_pause_stop(self) -> bool:
        """Check for pause/stop between EGATS iterations.

        Returns:
            True if stop was requested (caller should exit loop).
        """
        if self._stop_requested:
            return True

        if self._pause_requested:
            self._pause_requested = False
            self._set_state(AgentState.PAUSED, "Paused - waiting for input")
            self.sessions.update_status(SessionStatus.PAUSED)

            await self._resume_event.wait()
            self._resume_event.clear()

            if self._stop_requested:
                return True

            self._set_state(AgentState.RUNNING, "Resumed")
            self.sessions.update_status(SessionStatus.RUNNING)

            if self._pending_instruction:
                self.sessions.add_instruction(self._pending_instruction)
                self.events.emit_message(f"Injecting: {self._pending_instruction[:50]}...", "info")
                await self.backend.query(self._pending_instruction)
                self._pending_instruction = None

        return False

    # === Main Execution ===

    async def run(self, task: str, resume_session_id: str | None = None) -> dict[str, Any]:
        """Run agent with EGATS planning loop.

        Args:
            task: Task description for the agent.
            resume_session_id: Optional session ID to resume.

        Returns:
            Result dictionary with success, output, flags, etc.
        """
        # Reset state
        self._pause_requested = False
        self._stop_requested = False
        self._resume_event.clear()

        # Create or resume session
        if resume_session_id:
            session = self.sessions.load(resume_session_id)
            if not session:
                return {
                    "success": False,
                    "error": f"Session {resume_session_id} not found",
                }
            if not task:
                task = session.task
        else:
            session = self.sessions.create(
                target=self.config.target,
                task=task,
                model=self.config.llm_model,
            )

        # Initialize EGATS components
        self._init_egats()

        # Create backend if needed
        if self.backend is None:
            from excalibur.prompts.pentesting import get_ctf_prompt

            self.backend = ClaudeCodeBackend(
                working_directory=str(self.config.working_directory),
                system_prompt=get_ctf_prompt(self.config.custom_instruction),
                model=self.config.llm_model,
            )

        try:
            self._set_state(
                AgentState.RUNNING,
                "Connecting...",
                target=self.config.target,
                task=task,
            )

            # Connect (or resume)
            if resume_session_id and self.backend.supports_resume:
                backend_session = session.backend_session_id or resume_session_id
                await self.backend.resume(backend_session)
                self.events.emit_message(f"Resumed session {resume_session_id}", "info")
            else:
                await self.backend.connect()

            # Store backend session ID
            if self.backend.session_id:
                self.sessions.set_backend_session_id(self.backend.session_id)

            # Initialize attack tree
            self._attack_tree = self._planner.init_tree(self.config.target)

            # Run EGATS planning loop
            result = await self._egats_loop(task)

            return {
                "success": True,
                "output": "\n".join(result["output_parts"]),
                "flags_found": result["flags_found"],
                "success_detected": result.get("success_detected", False),
                "session_id": session.session_id,
                "cost_usd": session.total_cost_usd,
            }

        except Exception as e:
            self._set_state(AgentState.ERROR, str(e))
            self.sessions.set_error(str(e))
            self.sessions.update_status(SessionStatus.ERROR)
            return {"success": False, "error": str(e)}

        finally:
            if self.backend:
                await self.backend.disconnect()
            if self._state_store:
                self._state_store.close()

    async def _egats_loop(self, initial_task: str) -> dict[str, Any]:
        """Run the EGATS planning loop.

        This replaces the simple linear message loop with an evidence-guided
        attack tree search. Each iteration:
        1. Select node (UCB)
        2. Compute TDI
        3. Select mode (BFS/DFS/LLMDecide)
        4. Assemble context prompt
        5. Query backend
        6. Parse results -> update tree + state store
        7. Backpropagate promise scores
        8. Check pivot spawning + credential propagation
        9. Check pruning
        10. Check context compression

        Args:
            initial_task: The initial task description.

        Returns:
            Dict with output_parts and flags_found.
        """
        from excalibur.planner.models import NodeStatus
        from excalibur.prompts.summarize import SUMMARY_PROMPT

        output_parts: list[str] = []
        flags_found: list[str] = []
        tree = self._attack_tree
        budget = 40#self.config.max_budget

        self.sessions.update_status(SessionStatus.RUNNING)

        # EGATS iteration loop. The very first pass acts as "iteration
        # zero": the root node (the only active leaf right after
        # init_tree()) gets selected naturally, but is sent *initial_task*
        # verbatim instead of a synthesized EGATS query, since there's
        # nothing yet discovered for _build_egats_query's context/FOCUS
        # sections to describe. Every step after that -- TDI, mode,
        # backprop, state-store population, tree expansion, pruning,
        # compression -- runs identically for this and every later
        # iteration, so the initial exchange is no longer invisible to
        # the attack tree.
        while budget > 0 and not self._stop_requested and not self._success_detected:
            # Check for flags found -> goal reached
            if flags_found:
                logger.info("Flags found, continuing to verify completeness")

            is_first_iteration = tree.total_actions == 0

            # 1. Select node via UCB
            current_node = self._planner.select_next_node(tree)
            if current_node is None:
                self.events.emit_message("All attack tree branches exhausted", "warning")
                break

            current_node.status = NodeStatus.ACTIVE
            tree.active_node_id = current_node.id
            self.events.emit(
                Event(
                    EventType.TREE_NODE_SELECTED,
                    {"node_id": current_node.id, "description": current_node.description},
                )
            )

            # 2. Compute TDI (horizon estimated via a dedicated LLM query;
            # falls back to the deterministic tree-depth proxy on failure)
            context_load = 0.0
            if self._context_assembler:
                ctx = self._context_assembler.assemble(current_node, tree, "reconnaissance")
                context_load = self._context_assembler.get_context_load(ctx)

            llm_horizon = await self._estimate_horizon_llm(current_node, tree)

            tdi = self._planner.compute_tdi(current_node, tree, context_load, llm_horizon=llm_horizon)
            self.events.emit(
                Event(
                    EventType.TDI_COMPUTED,
                    {"node_id": current_node.id, "tdi_value": tdi.value},
                )
            )

            # 3. Select mode
            mode = self._planner.select_mode(tdi)
            self.events.emit(
                Event(
                    EventType.MODE_SELECTED,
                    {"mode": mode, "tdi_value": tdi.value},
                )
            )

            if is_first_iteration:
                # Use the initial task verbatim rather than a synthesized
                # EGATS query -- there's no prior context/findings for
                # _build_egats_query to assemble yet.
                query = initial_task
            else:
                # 4. Assemble context prompt
                context_prompt = ""
                if self._context_assembler:
                    context_prompt = self._context_assembler.assemble(
                        current_node, tree, mode, tdi.value
                    )

                # Build query from context + node description
                query = self._build_egats_query(current_node, mode, context_prompt, tdi.value)

            # 5. Check pause/stop before querying
            if await self._check_pause_stop():
                self.sessions.update_status(SessionStatus.PAUSED)
                return {"output_parts": output_parts, "flags_found": flags_found}

            # 6. Query backend
            self.events.emit_message("Query(\n" + query + "\n)End Query; Remaining budget: " + str(budget))  #added
            await self.backend.query(query)

            # 7. Process response and collect findings
            iteration_findings: list[str] = []
            flags_before = list(flags_found)  # snapshot before _process_message mutates it
            async for msg in self.backend.receive_messages():
                if await self._check_pause_stop():
                    self.sessions.update_status(SessionStatus.PAUSED)
                    return {
                        "output_parts": output_parts,
                        "flags_found": flags_found,
                    }
                await self._process_message(msg, output_parts, flags_found)
                # Collect text findings for tree expansion
                if msg.type == MessageType.TEXT and msg.content:
                    iteration_findings.append(msg.content)
                if self._success_detected:
                    # Stop consuming this response as soon as the marker
                    # appears rather than waiting for it to finish streaming.
                    break

            tree.total_actions += 1
            budget -= 1
            tree.budget_remaining = budget

            if self._success_detected:
                logger.info("Success marker detected — ending EGATS loop early.")
                break  # skip the summary round-trip / tree bookkeeping below; we're done

            # 7b. Ask for a structured JSON summary of new findings, to
            # populate the state store. This is a bookkeeping round-trip,
            # not part of the walkthrough narrative -- collect its text
            # directly rather than routing it through _process_message, so
            # it doesn't pollute output_parts or trigger flag/event noise.
            summary_parts: list[str] = []
            await self.backend.query(SUMMARY_PROMPT)
            async for msg in self.backend.receive_messages():
                if await self._check_pause_stop():
                    self.sessions.update_status(SessionStatus.PAUSED)
                    return {
                        "output_parts": output_parts,
                        "flags_found": flags_found,
                    }
                if msg.type == MessageType.TEXT and msg.content:
                    summary_parts.append(msg.content)

            # 8. Update tree with findings
            if iteration_findings:
                current_node.findings.extend(iteration_findings[:3])

            # 9. Backpropagate
            outcome = self._assess_outcome(iteration_findings, flags_before)
            self._planner.backpropagate(tree, current_node, outcome)
            self.events.emit(
                Event(
                    EventType.TREE_BACKPROPAGATE,
                    {
                        "node_id": current_node.id,
                        "outcome": outcome.value,
                        "promise": current_node.promise_score,
                    },
                )
            )

            # 10. Expand tree with child nodes for new findings, using the
            # structured JSON summary (also populates the state store).
            # Evidence levels are classified from the raw action-response
            # text (iteration_findings), per Appendix C -- the summary text
            # is a paraphrase and wouldn't contain the actual tool-output
            # patterns (e.g. nmap version strings, sqlmap "injectable").
            new_findings = self._extract_json_findings(summary_parts, iteration_findings)
            if new_findings:
                new_nodes = self._planner.expand_tree(tree, current_node, new_findings)
                if new_nodes:
                    self.events.emit(
                        Event(
                            EventType.TREE_NODE_EXPANDED,
                            {
                                "parent_id": current_node.id,
                                "new_nodes": [n.id for n in new_nodes],
                            },
                        )
                    )

            # 11. Check pruning
            pruned = self._planner.check_pruning(tree)
            if pruned:
                self.events.emit(
                    Event(
                        EventType.TREE_NODE_PRUNED,
                        {"pruned_ids": pruned},
                    )
                )

            # 12. Check context compression
            if (
                self._context_compressor
                and context_load > 0
                and self._context_compressor.should_compress(context_load)
            ):
                self._context_compressor.compress(tree, context_load)
                self.events.emit(
                    Event(
                        EventType.CONTEXT_COMPRESSED,
                        {"context_load": context_load},
                    )
                )

            # Mark current node as completed
            current_node.status = NodeStatus.COMPLETED

        # Finalize
        if self._success_detected:
            self._set_state(AgentState.COMPLETED, f"Success marker '{self.SUCCESS_MARKER}' detected")
            self.sessions.update_status(SessionStatus.COMPLETED)
        elif not self._stop_requested:
            self._set_state(AgentState.COMPLETED)
            self.sessions.update_status(SessionStatus.COMPLETED)
        else:
            self._set_state(AgentState.IDLE, "Stopped by user")
            self.sessions.update_status(SessionStatus.PAUSED)

        return {
            "output_parts": output_parts,
            "flags_found": flags_found,
            "success_detected": self._success_detected,
        }

    async def _estimate_horizon_llm(self, node: Any, tree: Any) -> float | None:
        """Ask the model to estimate remaining steps to the goal from *node*.

        Implements the horizon estimation dimension as an actual LLM
        judgment (per §4.3.1), rather than the deterministic tree-depth
        proxy in TDAComputer._estimate_horizon_fallback. This is a
        bookkeeping round-trip, like the SUMMARY_PROMPT query -- its
        response is parsed directly rather than routed through
        _process_message, so it doesn't pollute output_parts or trigger
        flag/event noise.

        Args:
            node: The attack node to estimate horizon for.
            tree: The full attack tree (for path context).

        Returns:
            A float in [0.0, 1.0] (0.0 = very close to goal, 1.0 = very
            far), or ``None`` if the query failed or the response couldn't
            be parsed -- callers should fall back to the structural proxy
            in that case (compute_tdi does this automatically when passed
            ``llm_horizon=None``).
        """
        import re

        from excalibur.prompts.tda_prompts import HORIZON_ESTIMATION_PROMPT

        path = tree.get_path_to_root(node.id)
        path_description = " -> ".join(
            n.description for n in reversed(path) if n.description
        ) or "(no path yet)"

        findings = node.findings[-5:] if node.findings else []
        findings_description = "; ".join(findings) if findings else "(none yet)"

        prompt = HORIZON_ESTIMATION_PROMPT.format(
            node_description=node.description or "(no description)",
            path_description=path_description,
            findings=findings_description,
        )

        try:
            response_parts: list[str] = []
            await self.backend.query(prompt)
            async for msg in self.backend.receive_messages():
                if msg.type == MessageType.TEXT and msg.content:
                    response_parts.append(msg.content)
        except Exception as e:
            self.events.emit_message(f"Horizon estimation query failed: {e}", "warning")
            return None

        combined = "".join(response_parts).strip()
        match = re.search(r"(\d*\.?\d+)", combined)
        if match is None:
            self.events.emit_message(
                f"Horizon estimation response had no parseable float: {combined[:100]!r}",
                "warning",
            )
            return None

        try:
            value = float(match.group(1))
        except ValueError:
            return None

        return max(0.0, min(1.0, value))

    def _build_egats_query(
        self,
        node: Any,
        mode: str,
        context: str,
        tdi_value: float,
    ) -> str:
        """Build a query for the backend based on EGATS state.

        Args:
            node: Current attack tree node.
            mode: Current mode (reconnaissance/exploitation/llm_decide).
            context: Assembled context from memory subsystem.
            tdi_value: Current TDI value.

        Returns:
            Query string for the backend.
        """
        from excalibur.prompts.tda_prompts import (
            BFS_RECONNAISSANCE_ADDENDUM,
            DFS_EXPLOITATION_ADDENDUM,
        )

        parts = []

        # Mode directive -- use the actual BFS/DFS addenda instead of the
        # previous ad-hoc one-line FOCUS text.
        if mode == "reconnaissance":
            parts.append(BFS_RECONNAISSANCE_ADDENDUM.format(tdi_value=tdi_value))
        elif mode == "exploitation":
            parts.append(DFS_EXPLOITATION_ADDENDUM.format(tdi_value=tdi_value))
        else:
            # No dedicated addendum exists for llm_decide -- keep a short
            # generic directive so the query isn't left without guidance.
            parts.append(
                f"MODE: LLM-DECIDE (TDI={tdi_value:.2f})\n"
                "The situation is ambiguous. Assess the current evidence and "
                "decide whether to enumerate further or exploit a known "
                "vulnerability, then proceed accordingly."
            )

        # Node description
        parts.append(f"\nCurrent objective: {node.description}")

        # Target host
        if node.host:
            parts.append(f"Target host: {node.host}")

        # Context from memory
        if context:
            parts.append(f"\n--- CONTEXT ---\n{context}\n--- END CONTEXT ---")

        # Previous findings on this node
        if node.findings:
            recent = node.findings[-3:]
            parts.append(
                "\nRecent findings on this path:\n" + "\n".join(f"- {f[:200]}" for f in recent)
            )

        return "\n".join(parts)

    def _assess_outcome(self, findings: list[str], flags_found: list[str]) -> Any:
        """Assess the outcome of an EGATS iteration.

        Args:
            findings: Text findings from the iteration.
            flags_found: List of flags found so far.

        Returns:
            ActionOutcome value.
        """
        from excalibur.planner.models import ActionOutcome

        # Check if new flags were found in this iteration
        combined = " ".join(findings)
        new_flags = self._detect_flags(combined)
        if any(f not in flags_found for f in new_flags):
            return ActionOutcome.SUCCESS

        # Check for meaningful progress indicators
        progress_keywords = [
            "found",
            "discovered",
            "vulnerable",
            "access",
            "shell",
            "credential",
            "password",
            "exploit",
            "port",
            "service",
            "version",
        ]
        combined_lower = combined.lower()
        hits = sum(1 for kw in progress_keywords if kw in combined_lower)
        if hits >= 3:
            return ActionOutcome.PARTIAL

        return ActionOutcome.FAILURE

    def _extract_findings(self, text_findings: list[str]) -> list[dict[str, Any]]:
        """Extract structured findings from text for tree expansion.

        Args:
            text_findings: Raw text findings from backend.

        Returns:
            List of finding dicts suitable for tree expansion.
        """
        findings = []
        combined = " ".join(text_findings).lower()

        # Look for host/service discoveries
        ip_pattern = r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
        port_pattern = r"\b(\d{1,5})/(tcp|udp)\b"

        ips = set(re.findall(ip_pattern, combined))
        ports = set(re.findall(port_pattern, combined))

        for ip in ips:
            findings.append(
                {
                    "description": f"Discovered host: {ip}",
                    "host": ip,
                    "evidence": 0.8,
                    "type": "observation",
                }
            )

        for port, proto in ports:
            findings.append(
                {
                    "description": f"Open port {port}/{proto}",
                    "evidence": 0.8,
                    "type": "observation",
                }
            )

        # Look for vulnerability indicators
        vuln_keywords = [
            "sql injection",
            "xss",
            "rce",
            "lfi",
            "rfi",
            "ssrf",
            "buffer overflow",
            "command injection",
            "authentication bypass",
        ]
        for kw in vuln_keywords:
            if kw in combined:
                findings.append(
                    {
                        "description": f"Potential vulnerability: {kw}",
                        "evidence": 0.5,
                        "type": "hypothesis",
                    }
                )

        return findings[:10]  # Limit expansion

    # Deterministic evidence-confidence rubric, per Appendix C. Returns only
    # the four canonical EvidenceLevel values (1.0/0.8/0.5/0.3) so results
    # are always valid for EvidenceLevel(...), which does not coerce
    # arbitrary floats to the nearest member.
    _EVIDENCE_SESSION_PATTERNS: ClassVar[list[str]] = [
        "session opened",
        "shell established",
        "logged in as",
        "authentication succeeded",
        "successful login",
        "connection established",
        "valid credentials",
        "authenticated as",
        "got a shell",
        "meterpreter session",
        "ssh connection succeeded",
        "login successful",
    ]
    _EVIDENCE_CONFIRMED_PATTERNS: ClassVar[list[str]] = [
        "injectable",
        "successfully exploited",
        "vulnerable to",
        "exploit succeeded",
        "rce confirmed",
        "confirmed vulnerable",
        "injection confirmed",
        "exploitation successful",
    ]
    _EVIDENCE_VERSION_PATTERN: ClassVar[str] = r"\bv?\d+\.\d+(?:\.\d+)?[a-z0-9]*\b"

    def _classify_evidence(
        self,
        raw_text: str,
        identifiers: list[str | None],
        has_version: bool = False,
    ) -> float:
        """Classify evidence confidence for an entity from raw tool-output text.

        Per Appendix C: nmap output containing an open port with a service
        version triggers version-matched confidence (0.5); sqlmap-style
        "injectable"/confirmed-exploitation language triggers confirmed
        injection (0.8); a successful session/login triggers valid
        credentials (1.0). Bare port/service identification with no
        version or confirmation language falls back to speculative (0.3).

        Args:
            raw_text: The raw action-response text for this iteration
                (not the paraphrased JSON summary -- that wouldn't contain
                the actual tool-output patterns this looks for).
            identifiers: Strings identifying the entity being scored (e.g.
                an IP, port, service name, or CVE ID). Used to narrow the
                search to lines actually mentioning this entity, so an
                unrelated confirmed exploit elsewhere in the same
                iteration's output doesn't inflate this entity's score.
            has_version: Whether the caller already knows a version string
                was associated with this entity (e.g. a service's
                ``version`` field was populated in the JSON summary),
                which alone is enough to qualify for PLAUSIBLE (0.5) even
                if the raw text search below doesn't independently find one.

        Returns:
            One of ``1.0``, ``0.8``, ``0.5``, or ``0.3``.
        """
        idents = [i for i in identifiers if i]

        if not raw_text:
            return 0.5 if has_version else 0.3

        lines = raw_text.splitlines()
        relevant_lines = [
            line for line in lines if any(ident.lower() in line.lower() for ident in idents)
        ]
        # If none of the identifiers appear anywhere (e.g. very short/odd
        # output), fall back to scanning the whole iteration's text rather
        # than scoring blind -- better an approximate match than none.
        context = "\n".join(relevant_lines).lower() if relevant_lines else raw_text.lower()

        if any(p in context for p in self._EVIDENCE_SESSION_PATTERNS):
            return 1.0
        if any(p in context for p in self._EVIDENCE_CONFIRMED_PATTERNS):
            return 0.8
        if has_version or re.search(self._EVIDENCE_VERSION_PATTERN, context):
            return 0.5
        return 0.3

    def _extract_json_findings(
        self,
        summary_parts: list[str],
        raw_action_text: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Parse a structured JSON summary response and populate the state store.

        Expects the backend's response to SUMMARY_PROMPT: a single JSON object
        with "hosts", "services", "credentials", "sessions", and
        "vulnerabilities" lists (see excalibur.prompts.summarize).

        Unlike the regex-based ``_extract_findings``, this also writes
        discovered entities into the Memory Subsystem's StateStore so they
        persist independently of the attack tree / conversation context.

        Args:
            summary_parts: Text blocks collected from the backend's response
                to the SUMMARY_PROMPT query. May be more than one block if
                the response was streamed/split.
            raw_action_text: Text blocks from the actual action/recon
                response for this iteration (i.e. ``iteration_findings``),
                used to classify evidence confidence per Appendix C's
                rubric. This is deliberately the raw response, not the
                summary -- the summary is a paraphrase and wouldn't contain
                the tool-output patterns (nmap version strings, sqlmap
                "injectable", etc.) the rubric looks for.

        Returns:
            List of finding dicts suitable for tree expansion (capped at 10).
            Returns an empty list if the response was empty or not valid,
            parseable JSON matching the expected schema.
        """
        from excalibur.memory.models import (
            CredentialEntity,
            HostEntity,
            ServiceEntity,
            SessionEntity,
            VulnerabilityEntity,
        )
        import json

        raw_text = "".join(raw_action_text) if raw_action_text else ""

        findings: list[dict[str, Any]] = []

        if not summary_parts:
            return findings

        combined = "".join(summary_parts).strip()
        if not combined:
            return findings

        try:
            data = json.loads(combined)
        except json.JSONDecodeError as e:
            self.events.emit_message(f"Summary response was not valid JSON: {e}", "error")
            return findings

        if self._state_store is None:
            return findings

        # --- Hosts ---
        for host in data.get("hosts", []):
            try:
                self._state_store.add_host(
                    HostEntity(
                        ip_address=host["ip_address"],
                        hostname=host.get("hostname") or None,
                    )
                )
                evidence = self._classify_evidence(
                    raw_text, [host["ip_address"], host.get("hostname")]
                )
                findings.append(
                    {
                        "description": f"Discovered host: {host['ip_address']}",
                        "host": host["ip_address"],
                        "evidence": evidence,
                        "type": "observation",
                    }
                )
            except (KeyError, TypeError) as e:
                self.events.emit_message(f"Skipping malformed host entry: {e}", "warning")

        # --- Services ---
        for service in data.get("services", []):
            try:
                host = self._state_store.get_host_by_ip(service["host_ip"])
                if host is None:
                    self.events.emit_message(
                        f"Skipping service on unknown host: {service.get('host_ip')}", "warning"
                    )
                    continue
                self._state_store.add_service(
                    ServiceEntity(
                        host_id=host.id,
                        port=int(service["port"]),
                        protocol=service.get("protocol", "tcp"),
                        service_name=service.get("service_name") or None,
                        version=service.get("version") or None,
                    )
                )
                evidence = self._classify_evidence(
                    raw_text,
                    [service["host_ip"], str(service["port"]), service.get("service_name")],
                    has_version=bool(service.get("version")),
                )
                findings.append(
                    {
                        "description": f"Open port {service['port']}/{service.get('protocol', 'tcp')}",
                        "host": service["host_ip"],
                        "evidence": evidence,
                        "type": "observation",
                    }
                )
            except (KeyError, TypeError, ValueError) as e:
                self.events.emit_message(f"Skipping malformed service entry: {e}", "warning")

        # --- Credentials ---
        for credential in data.get("credentials", []):
            try:
                valid_for: list[str] = []
                for ip in credential.get("valid_for", []):
                    host = self._state_store.get_host_by_ip(ip)
                    if host is not None:
                        valid_for.append(host.id)
                self._state_store.add_credential(
                    CredentialEntity(
                        username=credential["username"],
                        domain=credential.get("domain") or None,
                        valid_for=valid_for,
                        credential_type=credential.get("credential_type", "password"),
                        credential_value=credential.get("credential_value", ""),
                    )
                )
            except (KeyError, TypeError) as e:
                self.events.emit_message(f"Skipping malformed credential entry: {e}", "warning")

        # --- Sessions ---
        for session in data.get("sessions", []):
            try:
                host = self._state_store.get_host_by_ip(session["host_ip"])
                if host is None:
                    self.events.emit_message(
                        f"Skipping session on unknown host: {session.get('host_ip')}", "warning"
                    )
                    continue
                self._state_store.add_session(
                    SessionEntity(
                        host_id=host.id,
                        session_type=session.get("session_type", "shell"),
                        privilege_level=session.get("privilege_level", "user"),
                        active=bool(session.get("active", True)),
                    )
                )
            except (KeyError, TypeError) as e:
                self.events.emit_message(f"Skipping malformed session entry: {e}", "warning")

        # --- Vulnerabilities ---
        # Note: VulnerabilityEntity has no `service_name` field (only an
        # optional `service_id`, which we don't reliably have here), so the
        # service name is folded into the description instead of being
        # passed as an invalid keyword argument.
        for vuln in data.get("vulnerabilities", []):
            try:
                host = self._state_store.get_host_by_ip(vuln["host_ip"])
                if host is None:
                    self.events.emit_message(
                        f"Skipping vulnerability on unknown host: {vuln.get('host_ip')}", "warning"
                    )
                    continue
                service_name = vuln.get("service_name") or ""
                description = vuln.get("description", "")
                full_description = (
                    f"[{service_name}] {description}" if service_name else description
                )
                self._state_store.add_vulnerability(
                    VulnerabilityEntity(
                        host_id=host.id,
                        cve_id=vuln.get("cve_id") or None,
                        description=full_description,
                        exploitation_status=vuln.get("exploitation_status", "discovered"),
                    )
                )
                evidence = self._classify_evidence(
                    raw_text, [vuln["host_ip"], service_name, vuln.get("cve_id")]
                )
                findings.append(
                    {
                        "description": f"Potential vulnerability: {full_description[:150]}",
                        "host": vuln["host_ip"],
                        "evidence": evidence,
                        "type": "hypothesis",
                    }
                )
            except (KeyError, TypeError) as e:
                self.events.emit_message(f"Skipping malformed vulnerability entry: {e}", "warning")

        return findings[:10]  # Limit expansion

    async def _process_message(
        self,
        msg: AgentMessage,
        output_parts: list[str],
        flags_found: list[str],
    ) -> None:
        """Process a single agent message.

        Args:
            msg: Message to process.
            output_parts: List to append text output to.
            flags_found: List to append found flags to.
        """
        if msg.type == MessageType.TEXT:
            output_parts.append(msg.content)
            self.events.emit_message(msg.content)

            # Detect flags
            detected = self._detect_flags(msg.content)
            for flag in detected:
                if flag not in flags_found:
                    flags_found.append(flag)
                    self.sessions.add_flag(flag, msg.content[:200])
                    self.events.emit_flag(flag, msg.content[:200])

            # Detect the prompt-driven success marker (used for targets like
            # vulhub CVEs that have no flag to capture).
            if not self._success_detected and re.search(
                rf"\b{re.escape(self.SUCCESS_MARKER)}\b", msg.content
            ):
                self._success_detected = True
                logger.info(f"Success marker '{self.SUCCESS_MARKER}' detected in agent output.")
                self.events.emit_message(
                    f"Success marker '{self.SUCCESS_MARKER}' detected — ending run.", "success"
                )

        elif msg.type == MessageType.TOOL_START:
            if msg.tool_name == "Skill":
                skill_name = (msg.tool_args or {}).get("skill", "unknown")
                logger.info(f"Skill invoked: {skill_name}")
            self.events.emit_tool(
                status="start",
                name=msg.tool_name or "unknown",
                args=msg.tool_args,
            )

        elif msg.type == MessageType.TOOL_RESULT:
            self.events.emit_tool(
                status="complete",
                name=msg.tool_name or "unknown",
                result=msg.content,
            )

        elif msg.type == MessageType.RESULT:
            cost = msg.metadata.get("cost_usd", 0)
            if cost > 0:
                self.sessions.add_cost(cost)

    def _detect_flags(self, text: str) -> list[str]:
        """Detect potential flags in text."""
        flags = []
        for pattern in self.FLAG_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                flag = match.group(0)
                if flag not in flags:
                    flags.append(flag)
        return flags
