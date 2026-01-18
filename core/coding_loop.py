import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings_loader import reload_settings
from core.model_manager import ModelManager
from tools.coding_tools import get_tool_registry, parse_tool_invocations, tool_descriptions


class CodingLoop:
    def __init__(self, session_id: str, model_name: Optional[str] = None):
        self.session_id = session_id
        self.tools = get_tool_registry(session_id)
        settings = reload_settings()
        agent_settings = settings.get("agent", {})
        self.model_provider = agent_settings.get("model_provider", "gemini")
        self.model_name = model_name or agent_settings.get("default_model", "gemini-2.5-flash-lite")
        self.model_manager = ModelManager(self.model_name, provider=self.model_provider)

    def _build_system_prompt(self) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / "coding.md"
        base_prompt = prompt_path.read_text(encoding="utf-8")
        return base_prompt.format(tool_list_repr=tool_descriptions())

    def _format_conversation(self, messages: List[Dict[str, Any]]) -> str:
        lines = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)

    async def run_message(
        self,
        messages: List[Dict[str, Any]],
        max_tool_loops: int = 8,
    ) -> Dict[str, Any]:
        system_prompt = self._build_system_prompt()
        conversation_text = self._format_conversation(messages)

        tool_trace = []
        assistant_text = ""

        for _ in range(max_tool_loops):
            prompt = f"{system_prompt}\n\nConversation:\n{conversation_text}\n\nASSISTANT:"
            assistant_text = await self.model_manager.generate_text(prompt)
            tool_calls = parse_tool_invocations(assistant_text)
            if not tool_calls:
                return {
                    "assistant": assistant_text,
                    "tool_trace": tool_trace,
                }

            for name, args in tool_calls:
                if name not in self.tools:
                    tool_trace.append({"tool": name, "args": args, "error": "Unknown tool"})
                    continue
                try:
                    result = self.tools[name](**args)
                except Exception as exc:
                    result = {"error": str(exc)}
                tool_trace.append({"tool": name, "args": args, "result": result})
                messages.append(
                    {
                        "role": "user",
                        "content": f"tool_result({json.dumps(result)})",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                conversation_text = self._format_conversation(messages)

        return {
            "assistant": assistant_text or "Tool loop limit reached.",
            "tool_trace": tool_trace,
            "warning": "tool_loop_limit_reached",
        }
