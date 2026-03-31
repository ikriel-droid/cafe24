from __future__ import annotations

import json
from typing import Any, Sequence

import httpx

from app.ai.base import AIProvider, AIResultMetadata, AIUsage, ClassificationResult, DraftReplyResult
from app.ai.mock_provider import MockAIProvider
from app.ai.prompts import PromptBundle, build_classification_prompt, build_draft_reply_prompt
from app.models import Claim, ClaimCategory, ClaimMessage, ClaimUrgency, Policy


KNOWN_MODEL_PRICING_PER_1M_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
}


class OpenAIProvider(AIProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int,
        input_cost_per_1m_tokens: float | None = None,
        output_cost_per_1m_tokens: float | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.input_cost_per_1m_tokens = input_cost_per_1m_tokens
        self.output_cost_per_1m_tokens = output_cost_per_1m_tokens
        self._fallback = MockAIProvider()

    def classify_claim(self, claim: Claim, messages: Sequence[ClaimMessage]) -> ClassificationResult:
        prompt = build_classification_prompt(claim, messages)
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["category", "label", "urgency", "confidence", "rationale"],
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [category.value for category in ClaimCategory],
                },
                "label": {"type": "string"},
                "urgency": {"type": "string", "enum": [urgency.value for urgency in ClaimUrgency]},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "rationale": {"type": "string"},
            },
        }

        try:
            payload = self._request_json(prompt, response_schema_name="claim_classification", response_schema=schema)
            metadata = self._build_metadata(payload, prompt)
            return ClassificationResult(
                category=ClaimCategory(str(payload["category"]).strip()),
                label=str(payload["label"]).strip(),
                urgency=ClaimUrgency(str(payload["urgency"]).strip()),
                confidence=self._normalize_confidence(payload["confidence"]),
                rationale=str(payload["rationale"]).strip(),
                metadata=metadata,
            )
        except Exception as exc:
            fallback_result = self._fallback.classify_claim(claim, messages)
            fallback_result.metadata.requested_provider_name = "openai_responses"
            fallback_result.metadata.model_name = self.model
            fallback_result.metadata.prompt_key = prompt.prompt_key
            fallback_result.metadata.prompt_version = prompt.prompt_version
            fallback_result.metadata.fallback_used = True
            fallback_result.metadata.fallback_reason = str(exc)
            return fallback_result

    def draft_reply(
        self,
        claim: Claim,
        policy: Policy,
        messages: Sequence[ClaimMessage],
    ) -> DraftReplyResult:
        prompt = build_draft_reply_prompt(claim, policy, messages)
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["draft_reply", "confidence", "rationale"],
            "properties": {
                "draft_reply": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "rationale": {"type": "string"},
            },
        }

        try:
            payload = self._request_json(prompt, response_schema_name="claim_draft_reply", response_schema=schema)
            metadata = self._build_metadata(payload, prompt)
            return DraftReplyResult(
                draft_reply=str(payload["draft_reply"]).strip(),
                confidence=self._normalize_confidence(payload["confidence"]),
                rationale=str(payload["rationale"]).strip(),
                metadata=metadata,
            )
        except Exception as exc:
            fallback_result = self._fallback.draft_reply(claim, policy, messages)
            fallback_result.metadata.requested_provider_name = "openai_responses"
            fallback_result.metadata.model_name = self.model
            fallback_result.metadata.prompt_key = prompt.prompt_key
            fallback_result.metadata.prompt_version = prompt.prompt_version
            fallback_result.metadata.fallback_used = True
            fallback_result.metadata.fallback_reason = str(exc)
            return fallback_result

    def _request_json(
        self,
        prompt: PromptBundle,
        *,
        response_schema_name: str,
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "developer",
                    "content": [{"type": "input_text", "text": prompt.developer_message}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt.user_message}],
                },
            ],
        }
        if self._supports_structured_outputs():
            payload["text"] = {
                "format": {
                    "type": "json_schema",
                    "name": response_schema_name,
                    "schema": response_schema,
                    "strict": True,
                }
            }
        else:
            payload["input"].append(
                {
                    "role": "developer",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Return exactly one valid JSON object and no markdown fences.",
                        }
                    ],
                }
            )

        with httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            response = client.post("responses", json=payload)

        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI Responses API failed with status {response.status_code}: {response.text}")

        body = response.json()
        parsed_output = self._parse_output_json(body)
        parsed_output["_claimmate_usage"] = self._extract_usage(body)
        return parsed_output

    def _supports_structured_outputs(self) -> bool:
        return not self.model.endswith("-pro")

    def _parse_output_json(self, response_body: dict[str, Any]) -> dict[str, Any]:
        output_text = response_body.get("output_text")
        if not isinstance(output_text, str) or not output_text.strip():
            output_text = self._extract_output_text(response_body)

        normalized_text = output_text.strip()
        if normalized_text.startswith("```"):
            normalized_text = normalized_text.strip("`")
            if normalized_text.startswith("json"):
                normalized_text = normalized_text[4:].strip()
        parsed = json.loads(normalized_text)
        if not isinstance(parsed, dict):
            raise ValueError("OpenAI output must be a JSON object.")
        return parsed

    def _extract_output_text(self, response_body: dict[str, Any]) -> str:
        output_items = response_body.get("output")
        if not isinstance(output_items, list):
            raise ValueError("OpenAI response missing output_text.")

        fragments: list[str] = []
        for item in output_items:
            if not isinstance(item, dict):
                continue
            contents = item.get("content")
            if not isinstance(contents, list):
                continue
            for content in contents:
                if not isinstance(content, dict):
                    continue
                text_value = content.get("text")
                if isinstance(text_value, str):
                    fragments.append(text_value)
        combined = "\n".join(fragment for fragment in fragments if fragment.strip()).strip()
        if not combined:
            raise ValueError("OpenAI response contained no text output.")
        return combined

    def _extract_usage(self, response_body: dict[str, Any]) -> AIUsage:
        usage = response_body.get("usage")
        if not isinstance(usage, dict):
            return AIUsage()

        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))
        estimated_cost_usd = self._estimate_cost_usd(input_tokens=input_tokens, output_tokens=output_tokens)
        return AIUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd,
        )

    def _estimate_cost_usd(self, *, input_tokens: int, output_tokens: int) -> float:
        input_rate, output_rate = self._resolve_pricing()
        return round(((input_tokens / 1_000_000) * input_rate) + ((output_tokens / 1_000_000) * output_rate), 6)

    def _resolve_pricing(self) -> tuple[float, float]:
        if self.input_cost_per_1m_tokens is not None and self.output_cost_per_1m_tokens is not None:
            return self.input_cost_per_1m_tokens, self.output_cost_per_1m_tokens
        return KNOWN_MODEL_PRICING_PER_1M_TOKENS.get(self.model, (0.0, 0.0))

    def _build_metadata(self, payload: dict[str, Any], prompt: PromptBundle) -> AIResultMetadata:
        usage = payload.pop("_claimmate_usage", AIUsage())
        if not isinstance(usage, AIUsage):
            usage = AIUsage()
        return AIResultMetadata(
            provider_name="openai_responses",
            requested_provider_name="openai_responses",
            model_name=self.model,
            prompt_key=prompt.prompt_key,
            prompt_version=prompt.prompt_version,
            usage=usage,
        )

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Confidence must be numeric.") from exc
        return max(0.0, min(1.0, numeric))
