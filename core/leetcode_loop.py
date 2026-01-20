from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings_loader import reload_settings
from core.model_manager import ModelManager


class LeetCodeLoop:
    def __init__(self, model_name: Optional[str] = None):
        settings = reload_settings()
        agent_settings = settings.get("agent", {})
        self.model_provider = agent_settings.get("model_provider", "gemini")
        self.model_name = model_name or agent_settings.get("default_model", "gemini-2.5-flash-lite")
        self.model_manager = ModelManager(self.model_name, provider=self.model_provider)

    def _load_prompt(self, mode: str, problem_context: str) -> str:
        prompt_file = "leetcode_explain.md" if mode == "explain" else "leetcode_solve.md"
        prompt_path = Path(__file__).parent.parent / "prompts" / prompt_file
        base_prompt = prompt_path.read_text(encoding="utf-8")
        return base_prompt.format(problem_context=problem_context or "MISSING")

    def _format_history(self, messages: List[Dict[str, Any]]) -> str:
        lines = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(f"{role.upper()}: {content}")
        return "\n".join(lines)

    async def run(
        self,
        messages: List[Dict[str, Any]],
        mode: str,
        problem_context: str,
    ) -> str:
        system_prompt = self._load_prompt(mode, problem_context)
        history = self._format_history(messages)
        prompt = f"{system_prompt}\n\nConversation:\n{history}\n\nASSISTANT:"
        return await self.model_manager.generate_text(prompt)
