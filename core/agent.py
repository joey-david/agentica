import json
import yaml
import re
from pathlib import Path
from typing import Any

from core.memory import Memory
from core.inference import get_inference
from core.utils.display import Display, Colors

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
        self.init_prompt_text: str = yaml.safe_load(Path("core/prompts/initialization.yaml").read_text())["system"]
        self.step_prompt_yaml: dict[str, Any] = yaml.safe_load(Path("core/prompts/step.yaml").read_text())

        # Banner -----------------------------------------------------------------
        self.display.print_banner("AGENTICA TOOL AGENT INITIALIZED")

    # ------------------------------------------------------------------
    # UTILITY: pretty‑formatted list of tools
    # ------------------------------------------------------------------
    def tools_prompt(self) -> str:
        return "\n".join(tool.to_string() for tool in self.tools.values())

    # ------------------------------------------------------------------
    # STEP 0 : PLAN
    # ------------------------------------------------------------------
    def initialize_step(self) -> str:
        """Collect Plan from the LLM using the initialization prompt."""
        self.display.print_step_header("INITIALIZATION")

        prompt = "\n".join([
            self.persistent_prompt,
            self.user_prompt,
            self.init_prompt_text.format(tools_block=self.tools_prompt()),
        ])

        self._dbg_llm_input(prompt)
        response = get_inference(prompt)
        self._dbg_llm_output(response)

        parsed = self.parse_response(response)
        if "Plan" not in parsed:
            raise ValueError("Initialization failed – no Plan detected. Make sure your initialization prompt instructs the model to output one.")

        plan = parsed["Plan"].strip()
        self.display.print_step_header("PLAN")
        print(f"{Colors.BRIGHT_GREEN}PLAN:{Colors.RESET}\n{plan}\n")
        return plan

    # ------------------------------------------------------------------
    # MAIN LOOP
    # ------------------------------------------------------------------
    def run(self) -> str:
        plan = self.initialize_step()
        results_json = "{}"  # first iteration has no tool results

        for step in range(1, self.max_steps + 1):
            # 1) LLM TURN -------------------------------------------------------
            llm_raw = self.llm_step(plan, results_json)
            data = self.parse_response(llm_raw)

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
            action_dict = data.get("Action", {"actions": []})
            results_json = self.action_step(action_dict, step)

        self.display.print_max_steps_reached()
        return "Max steps reached without Final_Answer."

    # ------------------------------------------------------------------
    # LLM TURN (THOUGHT + ACTIONS + SUMMARY + STATE)
    # ------------------------------------------------------------------
    def llm_step(self, plan: str, results: str) -> str:
        tpl = self.step_prompt_yaml["template"]
        rendered = tpl.format(
            plan_block=plan,
            n=self.memory.summaries.maxlen,
            summaries_block=self.memory.get_summaries() or "None yet.",
            state_block=self.memory.get_state() or "None.",
            results_block=results or "No tool results yet.",
            tools_block=self.tools_prompt(),
        )
        full_prompt = "\n".join([
            self.persistent_prompt,
            self.user_prompt,
            self.step_prompt_yaml["system"],
            rendered,
        ])
        self._dbg_llm_input(full_prompt)
        response = get_inference(full_prompt)
        self._dbg_llm_output(response)
        return response

    # ------------------------------------------------------------------
    # TOOL EXECUTION LOOP
    # ------------------------------------------------------------------
    def action_step(self, actions: dict, step_num: int | None = None) -> str:
        self.display.print_step_header("ACTION", step_num)
        results: dict[str, Any] = {}
        call_count: dict[str, int] = {}

        for act in actions.get("actions", []):
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
                    results[key] = out
                except TypeError:
                    results[key] = str(out)
                self.display.print_tool_result(results[key])
            except Exception as e:
                err = f"Error executing {name}: {e}"
                self.display.print_error(err)
                results[key] = err

        return json.dumps({"results": results})

    # ------------------------------------------------------------------
    # RESPONSE PARSER
    # ------------------------------------------------------------------
    def parse_response(self, text: str) -> dict[str, Any]:
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
                out["Action"] = json.loads(m.group(1))
            except json.JSONDecodeError as e:
                raise ValueError(f"Malformed Actions JSON: {e}\n--- RAW \n{m.group(1)[:200]} …") from e

        if not out:
            raise ValueError("No recognised keys (Plan/Thought/Action/Summary/State/Final_Answer) in LLM response.")
        return out

    # ------------------------------------------------------------------
    # DEBUG HELPERS
    # ------------------------------------------------------------------
    def _dbg_llm_input(self, prompt: str) -> None:
        if self.debug_llm:
            print(f"\n{Colors.BRIGHT_GREEN}=== LLM INPUT ==={Colors.RESET}\n{prompt}\n")

    def _dbg_llm_output(self, resp: str) -> None:
        if self.debug_llm:
            print(f"\n{Colors.BRIGHT_BLACK}=== LLM OUTPUT ==={Colors.RESET}\n{resp}\n")