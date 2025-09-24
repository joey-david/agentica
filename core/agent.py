import json
import yaml
import re
from pathlib import Path
from typing import Any

from core.memory import Memory
from core.inference import get_inference
from core.utils.display import Display, Colors
from core.utils.llm_filters import format_yaml_prompt


MAX_PROMPT_CHARS = 200_000
DEFAULT_SECTION_LIMITS: dict[str, int] = {
    "persistent_section": 8_000,
    "user_section": 6_000,
    "plan_block": 10_000,
    "summaries_block": 8_000,
    "state_block": 4_000,
    "stored_results_keys": 2_000,
    "stored_results_block": 30_000,
    "recent_timeline_block": 8_000,
    "long_term_notes_block": 8_000,
    "knowledge_digest_block": 14_000,
    "telemetry_block": 6_000,
    "results_block": 40_000,
    "tools_block": 12_000,
}
PRUNE_ORDER: tuple[str, ...] = (
    "results_block",
    "stored_results_block",
    "knowledge_digest_block",
    "recent_timeline_block",
    "long_term_notes_block",
    "summaries_block",
    "plan_block",
)


class ToolCallingAgent:
    """Autonomous tool‑calling agent following the LLM <-> tools alternation,
    with a context-aware memory and a structured approach to problem solving.
    """

    def __init__(
        self,
        tools: list,
        persistent_prompt: str = "",
        user_prompt: str = "",
        memory_instance: Memory | None = None,
        max_steps: int = 20,
        history_length: int = 15,
        debug: bool = True,
        debug_llm: bool = True,
    ) -> None:
        # Public / config params --------------------------------------------------
        self.tools = {tool.name: tool for tool in tools}
        self.memory = memory_instance or Memory(history_length=history_length)
        self.persistent_prompt = persistent_prompt.strip()
        self.user_prompt = user_prompt.strip()
        self.max_steps = max_steps
        self.display = Display(debug=debug)
        self.debug_llm = True
        self.max_prompt_chars = MAX_PROMPT_CHARS
        self.section_limits: dict[str, int] = dict(DEFAULT_SECTION_LIMITS)

        # Load prompts -----------------------------------------------------------
        self.init_prompt_text: str = yaml.safe_load(Path("core/prompts/initialization.yaml").read_text())
        self.step_prompt_yaml: dict[str, Any] = yaml.safe_load(Path("core/prompts/step.yaml").read_text())

        # Banner -----------------------------------------------------------------
        self.display.print_banner("AGENTICA TOOL AGENT INITIALIZED")

    # ------------------------------------------------------------------
    # UTILITY: pretty‑formatted list of tools
    # ------------------------------------------------------------------
    def tools_prompt(self) -> str:
        return "\n//////\n".join(tool.to_string() for tool in self.tools.values())

    # ------------------------------------------------------------------
    # Prompt construction helpers
    # ------------------------------------------------------------------
    def _truncate_text(self, text: str, limit: int | None) -> str:
        """Clamp `text` to `limit` characters and append a truncation notice if needed."""
        normalized = (text or "").strip()
        if limit is None or len(normalized) <= limit:
            return normalized

        notice = f"\n\n[[Truncated automatically, removed {len(normalized) - limit} chars]]"
        kept = max(0, limit - len(notice))
        if kept:
            trimmed = normalized[:kept].rstrip()
        else:
            trimmed = ""
        return trimmed + notice

    def _prepare_prompt_sections(
        self,
        sections: dict[str, Any],
        overrides: dict[str, int] | None = None,
    ) -> dict[str, str]:
        """Apply per-section limits before rendering the final prompt."""
        limits = dict(self.section_limits)
        if overrides:
            limits.update({key: value for key, value in overrides.items() if value is not None})

        prepared: dict[str, str] = {}
        for key, value in sections.items():
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            prepared[key] = self._truncate_text(text, limits.get(key))
        return prepared

    def _build_prompt(
        self,
        *,
        yaml_file: str,
        sections: dict[str, Any],
        additional_context: dict[str, Any] | None = None,
    ) -> str:
        """Render a prompt that respects the global context budget."""

        prepared = self._prepare_prompt_sections(sections)
        prompt = format_yaml_prompt(
            yaml_file=yaml_file,
            sections=prepared,
            additional_context=additional_context,
        )

        if len(prompt) <= self.max_prompt_chars:
            return prompt

        # Progressive pruning: repeatedly shrink high-noise sections until budget fits.
        for _ in range(3):
            if len(prompt) <= self.max_prompt_chars:
                break
            for key in PRUNE_ORDER:
                if len(prompt) <= self.max_prompt_chars:
                    break
                if key not in prepared or not prepared[key]:
                    continue
                new_limit = max(1_000, len(prepared[key]) // 2)
                prepared[key] = self._truncate_text(prepared[key], new_limit)
                prompt = format_yaml_prompt(
                    yaml_file=yaml_file,
                    sections=prepared,
                    additional_context=additional_context,
                )

        if len(prompt) <= self.max_prompt_chars:
            return prompt

        notice = f"\n\n[[Prompt truncated to fit {self.max_prompt_chars} characters]]"
        kept = max(0, self.max_prompt_chars - len(notice))
        return prompt[:kept] + notice

    # ------------------------------------------------------------------
    # STEP 0 : PLAN
    # ------------------------------------------------------------------
    def initialize_step(self) -> str:
        """Collect Plan from the LLM using the initialization prompt."""
        self.display.print_step_header("INITIALIZATION")

        # Format the initialization prompt
        prompt = self._build_prompt(
            yaml_file="core/prompts/initialization.yaml",
            sections={
                "persistent_section": self.persistent_prompt,
                "user_section": self.user_prompt,
                "tools_block": self.tools_prompt(),
            },
        )

        self._dbg_llm_input(prompt)
        response = get_inference(prompt)
        self._dbg_llm_output(response)

        parsed = self.parse_response(response)
        if "Plan" not in parsed:
            raise ValueError("Initialization failed – no Plan detected.")

        plan_data = parsed["Plan"]
        if isinstance(plan_data, dict):
            plan = json.dumps(plan_data, indent=2)
        else:
            plan = str(plan_data).strip()

        self.display.print_step_header("PLAN")
        print(f"{Colors.BRIGHT_GREEN}PLAN:{Colors.RESET}\n{plan}\n")
        return plan

    # ------------------------------------------------------------------
    # LLM TURN (THOUGHT + ACTIONS + SUMMARY + STATE)
    # ------------------------------------------------------------------
    def llm_step(self, plan: str, results: str, retrieved_keys: list[str] | None = None) -> str:
        """Generate the next step using the step prompt."""
        memory_blocks = self.memory.snapshot_for_prompt()
        prompt_sections = {
            "persistent_section": self.persistent_prompt,
            "user_section": self.user_prompt,
            "plan_block": plan,
            **memory_blocks,
            "stored_results_block": self._format_stored_results(retrieved_keys),
            "results_block": results or "No tool results yet.",
            "tools_block": self.tools_prompt(),
        }

        rendered_prompt = self._build_prompt(
            yaml_file="core/prompts/step.yaml",
            sections=prompt_sections,
            additional_context={"n": self.memory.summaries.maxlen},
        )

        self._dbg_llm_input(rendered_prompt)
        response = get_inference(rendered_prompt)
        self._dbg_llm_output(response)
        return response

    # ------------------------------------------------------------------
    # TOOL EXECUTION LOOP
    # ------------------------------------------------------------------
    def action_step(self, actions: dict, step_num: int | None = None) -> str:
        results: dict[str, Any] = {}
        call_count: dict[str, int] = {}

        # Handle both nested object with "Action" key and direct array
        action_list = []
        if isinstance(actions, list):
            action_list = actions
        elif isinstance(actions, dict):
            if "Actions" in actions and isinstance(actions["Actions"], list):
                action_list = actions["Actions"]
            elif "actions" in actions and isinstance(actions["actions"], list):
                action_list = actions["actions"]

        for act in action_list:
            # Case-insensitive key extraction
            name = None
            args = {}
            
            # Try different case variations for tool name
            for key in ["tool", "Tool", "TOOL", "tool_name", "Tool_Name"]:
                if key in act:
                    name = act[key]
                    break
            
            # Try different case variations for arguments
            for key in ["args", "Args", "ARGS", "arguments", "Arguments", "ARGUMENTS"]:
                if key in act:
                    args = act[key]
                    break
            
            if name is None:
                self.display.print_error("Error: No tool name provided in action.")
                continue  # Skip if no tool name found

            # unique key if tool called multiple times
            idx = call_count.get(name, 0)
            call_count[name] = idx + 1
            key = f"{name}_{idx}" if idx else name
            
            if name not in self.tools:
                results[key] = f"Error: Tool '{name}' not found."
                self.memory.record_tool_event(
                    name or "<unknown>",
                    success=False,
                    info={"error": "Tool not registered"}
                )
                continue

            self.display.print_tool_call(name, ", ".join(f"{k}={v!r}" for k, v in args.items()))
            try:
                result = self.tools[name](**args)
                success_flag = True
                cache_hit = None
                telemetry_details = {}
                if isinstance(result, dict) and "_telemetry" in result:
                    telemetry_details = result.get("_telemetry") or {}
                    success_flag = telemetry_details.get("success", True)
                    cache_hit = telemetry_details.get("cache_hit")
                    result = {k: v for k, v in result.items() if k != "_telemetry"}
                # Convert non-serializable objects to strings
                if hasattr(result, '__dict__') or str(type(result)).startswith('<'):
                    results[key] = str(result)
                else:
                    results[key] = result
                self.memory.record_tool_event(
                    name,
                    success=success_flag,
                    cache_hit=cache_hit,
                    info=telemetry_details or None,
                )
            except Exception as e:
                results[key] = f"Error: {e}"
                self.memory.record_tool_event(name, success=False, info={"error": str(e)})

        return json.dumps({"results": results}, default=str)
    
    # ------------------------------------------------------------------
    # MAIN LOOP
    # ------------------------------------------------------------------
    def run(self, user_prompt: str | None = None) -> str:
        if user_prompt is not None:
            self.user_prompt = str(user_prompt).strip()
        if not self.user_prompt:
            raise ValueError("User prompt must be provided before running the agent.")

        startup_snapshot = self.memory.startup_report()
        self.memory.add_structured_entry("Startup", startup_snapshot, step=0)
        if not self.memory.get_state():
            self.memory.set_state(f"Startup snapshot: {startup_snapshot}", step=0)

        plan = self.initialize_step()
        results_json = "{}"  # first iteration has no tool results
        retrieved_keys = None  # Start with no retrieved keys
        last_results_dict: dict[str, Any] = {}

        for step in range(1, self.max_steps + 1):
            self.display.print_step_header("Thinking", step)
            # 1) LLM TURN -------------------------------------------------------
            llm_raw = self.llm_step(plan, results_json, retrieved_keys)
            data = self.parse_response(llm_raw)
            thought = self._extract_thought_text(data)
            if self.debug_llm:
                if thought:
                    self.display.print_thought(thought)
                else:
                    self.display.print_thought("(No Thought provided in model response)")

            # Process memory commands -------------------------------------------
            # Store new results if requested
            if "StoreResults" in data and isinstance(data["StoreResults"], dict):
                for k, v in data["StoreResults"].items():
                    self.memory.store_result(k, v)
                    self.display.print_memory_update("STORE", f"{k} = {v}")
            
            # Get specific results if requested
            retrieved_keys = None
            if "RetrieveResults" in data and isinstance(data["RetrieveResults"], list):
                retrieved_keys = data["RetrieveResults"]
                self.display.print_memory_update("RETRIEVE", f"Keys: {retrieved_keys}")
            
            # Delete results if requested
            if "DeleteResults" in data and isinstance(data["DeleteResults"], list):
                for key in data["DeleteResults"]:
                    self.memory.clear_stored_result(key)
                    self.display.print_memory_update("DELETE", f"Key: {key}")

            # Book‑keeping ------------------------------------------------------
            summary = data.get("Summary", "")
            state = data.get("State", "")
            if summary:
                self.memory.add_summary(summary, step=step)
            if state:
                self.memory.set_state(state, step=step)

            # Termination check ------------------------------------------------
            if "Final_Answer" in data:
                final_answer = data["Final_Answer"]
                self.memory.add_structured_entry("FinalAnswer", final_answer, step=step)
                self.memory.remember_step(
                    step,
                    thought=thought,
                    actions=[],
                    results=last_results_dict or None,
                )
                self.display.print_step_header("FINAL ANSWER")
                print(final_answer)
                return final_answer

            # 2) TOOL TURN ------------------------------------------------------
            action_dict = None
            actions_for_memory: list[str] = []
            if isinstance(data.get("Actions"), list):
                action_dict = {"Actions": data["Actions"]}
                actions_for_memory = self._actions_to_memory_strings(data["Actions"])
            elif isinstance(data.get("Actions"), dict):
                raw_actions = data["Actions"]
                if isinstance(raw_actions.get("Actions"), list):
                    inner_actions = raw_actions["Actions"]
                    action_dict = raw_actions
                elif isinstance(raw_actions.get("actions"), list):
                    inner_actions = raw_actions["actions"]
                    action_dict = {"Actions": inner_actions}
                else:
                    inner_actions = [raw_actions]
                    action_dict = {"Actions": inner_actions}
                actions_for_memory = self._actions_to_memory_strings(inner_actions)
            elif "actions" in data:
                action_dict = {"Actions": data["actions"]}
                actions_for_memory = self._actions_to_memory_strings(data["actions"])
            else:
                self.display.print_no_tool_call()
                self.memory.remember_step(step, thought=thought, actions=[], results=None)
                last_results_dict = {}
                results_json = "{}"
                continue

            self.display.print_step_header("Action", step)
            results_json = self.action_step(action_dict, step)
            last_results_dict = self._parse_results(results_json)
            self.memory.set_action_results(last_results_dict)
            self.memory.remember_step(
                step,
                thought=thought,
                actions=actions_for_memory,
                results=last_results_dict or None,
            )

        self.display.print_max_steps_reached()
        return "Max steps reached without Final_Answer."

    # ------------------------------------------------------------------
    # RESPONSE PARSER
    # ------------------------------------------------------------------
    def parse_response(self, text: str) -> dict[str, Any]:
        # First try to parse the entire response as JSON
        text = self.normalize_llm_response(text)
        try:
            json_data = json.loads(text)
            out = {}
            if isinstance(json_data, dict):
                lowered = {k.lower(): k for k in json_data}
                for key in [
                    "Plan",
                    "Thought",
                    "Summary",
                    "State",
                    "Final_Answer",
                    "Actions",
                    "StoreResults",
                    "RetrieveResults",
                    "DeleteResults",
                ]:
                    target = lowered.get(key.lower())
                    if target is not None:
                        out[key] = json_data[target]
            else:
                return {}
            return out

        except json.JSONDecodeError:
            pass
            
        # Original regex-based parsing for non-JSON responses
        patterns = {
            "Plan": r"Plan:?\s*\{?(.*?)\}?($|\n\n)",
            "Thought": r"Thought:?\s*\{?(.*?)\}?($|\n\n|Action:)",
            "Summary": r"Summary:?\s*\{?(.*?)\}?($|\n\n)",
            "State": r"State:?\s*\{?(.*?)\}?($|\n\n)",
            "Final_Answer": r"Final_Answer:?\s*\{?(.*?)\}?($|\n\n)",
        }
        out: dict[str, Any] = {}
        for key, pat in patterns.items():
            if m := re.search(pat, text, re.DOTALL | re.IGNORECASE):
                out[key] = m.group(1).strip()

        # Actions --------------------------------------------------------------
        if m := re.search(r"Action:?\s*(\{.*\})", text, re.DOTALL):
            try:
                out["Actions"] = json.loads(m.group(1))
            except json.JSONDecodeError:
                self.display.print_error("Warning: Could not parse Action JSON.")

        if not out:
            self.display.print_error("Warning: Could not parse LLM response.")
        return out
    
    @staticmethod
    def _parse_results(results_json: str) -> dict[str, Any]:
        try:
            payload = json.loads(results_json)
        except (json.JSONDecodeError, TypeError):
            return {}
        results = payload.get("results") if isinstance(payload, dict) else None
        return results if isinstance(results, dict) else {}

    @staticmethod
    def _stringify_for_display(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value).strip()

    def _extract_thought_text(self, data: dict[str, Any]) -> str:
        for key in ("Thought", "thought", "THOUGHT", "Reasoning", "reasoning"):
            if key in data:
                text = self._stringify_for_display(data[key])
                if text:
                    return text
        return ""

    def normalize_llm_response(self, text: str) -> str:
        """Remove Markdown code block formatting and return clean JSON."""
        if text.startswith('```') and '```' in text[3:]:
            text = re.sub(r'```(json)?', '', text, count=1)
            text = re.sub(r'```', '', text, count=1)
        return text.strip()

    def _actions_to_memory_strings(self, actions: list[Any]) -> list[str]:
        formatted: list[str] = []
        for action in actions:
            if not isinstance(action, dict):
                formatted.append(str(action))
                continue

            name = self._extract_action_tool(action)
            args = self._extract_action_args(action)

            if not name:
                formatted.append(json.dumps(action, ensure_ascii=False))
                continue

            if args:
                arg_str = ", ".join(f"{k}={v!r}" for k, v in args.items())
                formatted.append(f"{name}({arg_str})")
            else:
                formatted.append(name)
        return formatted

    @staticmethod
    def _extract_action_tool(action: dict[str, Any]) -> str | None:
        for key in ["tool", "Tool", "TOOL", "tool_name", "Tool_Name"]:
            if key in action:
                value = action[key]
                if value is None:
                    continue
                return str(value)
        return None

    @staticmethod
    def _extract_action_args(action: dict[str, Any]) -> dict[str, Any]:
        for key in ["args", "Args", "ARGS", "arguments", "Arguments", "ARGUMENTS"]:
            value = action.get(key)
            if isinstance(value, dict):
                return value
        return {}

    def _format_stored_results_keys(self) -> str:
        """Format the stored results keys for the prompt."""
        keys = self.memory.get_stored_results_keys()
        if not keys:
            return "No results stored yet."
        return ", ".join(keys)

    def _format_stored_results(self, keys: list[str] | None = None) -> str:
        """Format specific stored results or a message about available keys."""
        if keys is None:
            return "You can request specific results by using 'RetrieveResults': [key1, key2] in your response."
        
        result = []
        for key in keys:
            value = self.memory.get_stored_result(key)
            result.append(f'### {key}:\n{value}')
        
        if not result:
            return "No results found for the requested keys."
        return "\n\n".join(result)

    # debug helpers
    def _dbg_llm_input(self, prompt: str) -> None:
        # Suppress prompt contents in debug mode to avoid leaking full agent input.
        return

    def _dbg_llm_output(self, resp: str) -> None:
        if self.debug_llm:
            self.display.print_llm_output(resp)
