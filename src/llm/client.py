"""
LLM Client - Wraps Anthropic Claude API for all agent reasoning.

Features:
- Response caching (avoid duplicate API calls for same prompts)
- Token usage tracking (monitor costs)
- Model selection per task (haiku for cheap tasks, sonnet for code)
- Graceful error handling
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Handle anthropic import
try:
    import anthropic
except ImportError:
    raise ImportError(
        "anthropic package not installed. Run: pip install anthropic"
    )

logger = logging.getLogger(__name__)

# Cost per 1M tokens (approximate, as of 2024)
MODEL_COSTS = {
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
}


class LLMClient:
    """
    Anthropic Claude client with caching and cost tracking.

    Uses:
    - Haiku for analysis/planning tasks (cheap, fast)
    - Sonnet for code generation (higher quality)
    - Local file cache to avoid repeat API calls
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "claude-sonnet-4-6",
        cache_dir: str = ".cache",
    ):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. "
                "Set it in .env or pass via --api-key flag."
            )
        self._default_model = default_model
        self._client = anthropic.Anthropic(api_key=self._api_key)

        # Cache setup
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(exist_ok=True)

        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.api_calls = 0

    def ask(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model: Optional[str] = None,
        use_cache: bool = True,
    ) -> str:
        """
        Send a prompt to Claude and get a text response.
        Results are cached locally to save API credits on repeat runs.
        """
        model = model or self._default_model

        # Check cache first
        if use_cache:
            cache_key = self._cache_key(model, system_prompt, user_prompt)
            cached = self._get_cached(cache_key)
            if cached is not None:
                logger.info(f"  [cache hit] Saved an API call (model: {model})")
                return cached

        # Call API
        logger.debug(f"LLM request ({model}): {user_prompt[:80]}...")

        message = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        response_text = message.content[0].text

        # Track usage
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.api_calls += 1

        costs = MODEL_COSTS.get(model, {"input": 3.0, "output": 15.0})
        call_cost = (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000
        self.total_cost_usd += call_cost

        logger.info(
            f"  [API] {model} | {input_tokens}+{output_tokens} tokens | ${call_cost:.4f}"
        )

        # Cache the response
        if use_cache:
            self._set_cached(cache_key, response_text)

        return response_text

    def ask_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
        model: Optional[str] = None,
        use_cache: bool = True,
    ) -> dict:
        """
        Send a prompt and parse the response as JSON.
        Handles markdown fences and partial JSON extraction.
        """
        full_system = (
            system_prompt + "\n\n"
            "IMPORTANT: Respond ONLY with valid JSON. "
            "No markdown code fences, no text outside the JSON object."
        )

        response_text = self.ask(
            full_system, user_prompt, max_tokens, temperature,
            model=model, use_cache=use_cache,
        )

        return self._parse_json(response_text)

    def get_usage_report(self) -> str:
        """Return a summary of API usage and cost."""
        return (
            f"API Calls: {self.api_calls} | "
            f"Tokens: {self.total_input_tokens:,} in + {self.total_output_tokens:,} out | "
            f"Cost: ${self.total_cost_usd:.4f}"
        )

    # --- Caching Methods ---

    def _cache_key(self, model: str, system_prompt: str, user_prompt: str) -> str:
        """Generate a unique cache key from the request parameters."""
        content = f"{model}|{system_prompt}|{user_prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[str]:
        """Retrieve a cached response if it exists."""
        cache_file = self._cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                return data.get("response")
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    def _set_cached(self, key: str, response: str) -> None:
        """Store a response in the local cache."""
        cache_file = self._cache_dir / f"{key}.json"
        cache_file.write_text(
            json.dumps({"response": response}, ensure_ascii=False),
            encoding="utf-8",
        )

    def clear_cache(self) -> int:
        """Clear all cached responses. Returns number of files deleted."""
        count = 0
        for f in self._cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        return count

    # --- JSON Parsing ---

    def _parse_json(self, response_text: str) -> dict:
        """Parse JSON from Claude's response, handling common formatting issues."""
        cleaned = response_text.strip()

        # Remove markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.strip() == "```" and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            cleaned = "\n".join(json_lines)

        # Try direct parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in the text
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(response_text[start:end])
            except json.JSONDecodeError:
                # JSON might be truncated — try to fix common issues
                json_str = response_text[start:end]
                # Try adding missing closing brackets
                fixed = self._fix_truncated_json(json_str)
                if fixed:
                    return fixed

        # Try to find JSON array
        start = response_text.find("[")
        end = response_text.rfind("]") + 1
        if start != -1 and end > start:
            try:
                arr = json.loads(response_text[start:end])
                return {"items": arr}
            except json.JSONDecodeError:
                pass

        logger.warning("Failed to parse LLM response as JSON")
        return {"raw_response": response_text}

    def _fix_truncated_json(self, json_str: str) -> dict | None:
        """Attempt to fix truncated JSON by closing open brackets/braces."""
        # Count unclosed brackets
        opens = json_str.count("{") - json_str.count("}")
        open_arrays = json_str.count("[") - json_str.count("]")

        if opens <= 0 and open_arrays <= 0:
            return None

        # Try to close them
        # First remove any trailing comma or incomplete value
        fixed = json_str.rstrip()
        if fixed.endswith(","):
            fixed = fixed[:-1]
        # Remove incomplete string value
        if fixed.count('"') % 2 != 0:
            # Find last complete key-value pair
            last_quote = fixed.rfind('"')
            if last_quote > 0:
                fixed = fixed[:last_quote+1]

        # Close arrays then objects
        fixed += "]" * max(0, open_arrays)
        fixed += "}" * max(0, opens)

        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None
