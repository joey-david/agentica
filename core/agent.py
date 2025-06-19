import json
import yaml
import re
from pathlib import Path
from typing import Any

from core.memory import Memory
from core.inference import get_inference
from core.utils.display import Display, Colors
from core.utils.llm_filters import format_yaml_prompt, remove_repeating_substrings

# -----------------------------------------------------------------------------
#  The Agent
# -----------------------------------------------------------------------------

class ToolCallingAgent:
    """Autonomous tool‑calling agent following the LLM ↔ tools alternation,
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
        debug_llm: bool = False,
    ) -> None:
        # Public / config params --------------------------------------------------
        self.tools = {tool.name: tool for tool in tools}
        self.memory = memory_instance or Memory(history_length=history_length)
        self.persistent_prompt = persistent_prompt.strip()
        self.user_prompt = user_prompt.strip()
        self.max_steps = max_steps
        self.display = Display(debug=debug)
        self.debug_llm = debug_llm

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
    # STEP 0 : PLAN
    # ------------------------------------------------------------------
    def initialize_step(self) -> str:
        """Collect Plan from the LLM using the initialization prompt."""
        self.display.print_step_header("INITIALIZATION")

        # Format the initialization prompt
        prompt = format_yaml_prompt(
            yaml_file="core/prompts/initialization.yaml",
            sections={
                "persistent_section": self.persistent_prompt,
                "user_section": self.user_prompt,
                "tools_block": self.tools_prompt(),
            }
        )

        self._dbg_llm_input(prompt)
        response = get_inference(prompt)
        self._dbg_llm_output(response)

        parsed = self.parse_response(response)
        if "Plan" not in parsed:
            raise ValueError("Initialization failed – no Plan detected.")

        plan = parsed["Plan"].strip()
        self.display.print_step_header("PLAN")
        print(f"{Colors.BRIGHT_GREEN}PLAN:{Colors.RESET}\n{plan}\n")
        return plan

    # ------------------------------------------------------------------
    # LLM TURN (THOUGHT + ACTIONS + SUMMARY + STATE)
    # ------------------------------------------------------------------
    def llm_step(self, plan: str, results: str) -> str:
        """Generate the next step using the step prompt."""
        rendered_prompt = format_yaml_prompt(
            yaml_file="core/prompts/step.yaml",
            sections={
                "system_section": self.init_prompt_text,
                "persistent_section": self.persistent_prompt,
                "user_section": self.user_prompt,
                "plan_block": plan,
                "summaries_block": self.memory.get_summaries() or "None yet.",
                "state_block": self.memory.get_state() or "None yet.",
                "stored_results_keys": self._format_stored_results_keys(),
                "stored_results_block": self._format_stored_results(),
                "results_block": results or "No tool results yet.",
                "tools_block": self.tools_prompt(),
            },
            additional_context={"n": self.memory.summaries.maxlen}
        )

        self._dbg_llm_input(rendered_prompt)
        response = get_inference(rendered_prompt)
        self._dbg_llm_output(response)
        return response

    # ------------------------------------------------------------------
    # TOOL EXECUTION LOOP
    # ------------------------------------------------------------------
    def action_step(self, actions: dict, step_num: int | None = None) -> str:
        self.display.print_step_header("ACTION", step_num)
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
            name = act.get("tool")
            args = act.get("args", {})
            if name not in self.tools:
                msg = f"Error: tool '{name}' not found."
                self.display.print_error(msg)
                results[name] = msg
                continue

            # unique key if tool called multiple times
            idx = call_count.get(name, 0)
            call_count[name] = idx + 1
            key = f"{name}_{idx}" if idx else name

            self.display.print_tool_call(name, ", ".join(f"{k}={v!r}" for k, v in args.items()))
            try:
                out = self.tools[name](**args)
                try:
                    json.dumps(out)  # serialisable?
                    results[key] = remove_repeating_substrings(out)
                except TypeError:
                    results[key] = str(out)
                self.display.print_tool_result(results[key])
            except Exception as e:
                err = f"Error executing {name}: {e}"
                self.display.print_error(err)
                results[key] = err

        return json.dumps({"results": results})
    
    # ------------------------------------------------------------------
    # MAIN LOOP
    # ------------------------------------------------------------------
    def run(self) -> str:
        plan = self.initialize_step()
        results_json = "{}"  # first iteration has no tool results
        retrieved_keys = None  # Start with no retrieved keys

        for step in range(1, self.max_steps + 1):
            # 1) LLM TURN -------------------------------------------------------
            llm_raw = self.llm_step(plan, results_json)
            data = self.parse_response(llm_raw)

            # Process memory commands -------------------------------------------
            # Store new results if requested
            if "StoreResults" in data and isinstance(data["StoreResults"], dict):
                for key, value in data["StoreResults"].items():
                    self.memory.store_result(key, value)
                    self.display.print_memory_operation(f"Stored result: {key}")
            
            # Get specific results if requested
            retrieved_keys = None
            if "RetrieveResults" in data and isinstance(data["RetrieveResults"], list):
                retrieved_keys = data["RetrieveResults"]
                self.display.print_memory_operation(f"Retrieved keys: {', '.join(retrieved_keys)}")
            
            # Delete results if requested
            if "DeleteResults" in data and isinstance(data["DeleteResults"], list):
                for key in data["DeleteResults"]:
                    self.memory.clear_stored_result(key)
                    self.display.print_memory_operation(f"Deleted result: {key}")

            # Book‑keeping ------------------------------------------------------
            if summary := data.get("Summary", ""):
                self.memory.add_summary(summary)
            if state := data.get("State", ""):
                self.memory.set_state(state)

            # Termination check ------------------------------------------------
            if "Final_Answer" in data:
                answer = data["Final_Answer"].strip()
                self.display.print_step_header("FINAL ANSWER")
                self.display.print_final_answer(answer)
                return answer


            # 2) TOOL TURN ------------------------------------------------------
            if isinstance(data.get("Actions"), list):
                # Direct array format: "Actions": [...]
                action_dict = data["Actions"]
            elif isinstance(data.get("Actions"), dict):
                # Nested format: "Actions": {"actions": [...]}
                action_dict = data["Actions"]
            elif "actions" in data:
                # Lowercase actions key
                action_dict = data["actions"]
            else:
                raise ValueError("No valid Actions found in LLM response.")

            results_json = self.action_step(action_dict, step)

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
            
            # Extract known keys from JSON
            for key in ["Plan", "Thought", "Summary", "State", "Final_Answer", "Actions"]:
                if key in json_data:
                    out[key] = json_data[key]
                
            if out:
                return out
        except json.JSONDecodeError:
            # Fall back to regex parsing if not valid JSON
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
            if m := re.search(pat, text, re.DOTALL):
                out[key] = m.group(1).strip()

        # Actions --------------------------------------------------------------
        if m := re.search(r"Action:?\s*(\{.*\})", text, re.DOTALL):
            try:
                out["Actions"] = json.loads(m.group(1))
            except json.JSONDecodeError as e:
                raise ValueError(f"Malformed Actions JSON: {e}\n--- RAW \n{m.group(1)[:200]} …") from e

        if not out:
            raise ValueError("No recognised keys (Plan/Thought/Action/Summary/State/Final_Answer) in LLM response.")
        return out
    
    def normalize_llm_response(self, text: str) -> str:
        """Remove Markdown code block formatting and return clean JSON."""
        if text.startswith('```') and '```' in text[3:]:
            match = re.search(r'```(?:json)?\n(.*?)\n```', text, re.DOTALL)
            if match:
                return match.group(1).strip()
        return text.strip()

    def _format_stored_results_keys(self) -> str:
        """Format the stored results keys for the prompt."""
        keys = self.memory.get_stored_results_keys()
        if not keys:
            return "No stored results available."
        return ", ".join(keys)

    def _format_stored_results(self, keys=None) -> str:
        """Format specific stored results or a message about available keys."""
        if keys is None:
            return "To view stored results, use RetrieveResults with specific keys."
        
        result = []
        for key in keys:
            value = self.memory.get_stored_result(key)
            if value is not None:
                # Format the value based on its type
                if isinstance(value, (list, dict)):
                    formatted_value = json.dumps(value, indent=2)[:1000]  # Limit size
                    if len(json.dumps(value)) > 1000:
                        formatted_value += "... [truncated]"
                else:
                    formatted_value = str(value)[:1000]
                    if len(str(value)) > 1000:
                        formatted_value += "... [truncated]"
                result.append(f"{key}: {formatted_value}")
        
        if not result:
            return "No results found for the requested keys."
        return "\n\n".join(result)

    # ------------------------------------------------------------------
    # DEBUG HELPERS
    # ------------------------------------------------------------------
    def _dbg_llm_input(self, prompt: str) -> None:
        if self.debug_llm:
            # Lighter gray (ANSI color 250), dim, italic
            print(f"\n\033[38;5;243m\033[2m\033[3m=== LLM INPUT ===\n{prompt}\n\033[0m")

    def _dbg_llm_output(self, resp: str) -> None:
        if self.debug_llm:
            # Even lighter gray (ANSI color 252), dim, italic
            print(f"\n\033[38;5;245m\033[2m\033[3m=== LLM OUTPUT ===\n{resp}\n\033[0m")