# ABOUTME: Token usage tracking and cost estimation across simmer runs.
# ABOUTME: Accumulates per-call usage by model and role, computes estimated cost.

"""Usage tracking for simmer runs.

Captures input/output tokens per API call, tagged by model and role
(generator, judge, clerk). Computes estimated cost using public pricing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Pricing per 1M tokens (USD) — update as pricing changes
PRICING: dict[str, tuple[float, float]] = {
    # (input_per_1M, output_per_1M)
    # Anthropic / Bedrock
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-haiku-4-5": (0.80, 4.00),
    "claude-opus-4-6": (15.00, 75.00),
    "claude-opus-4-5": (15.00, 75.00),
    # Bedrock IDs map to same pricing
    "us.anthropic.claude-sonnet-4-6": (3.00, 15.00),
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0": (3.00, 15.00),
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": (0.80, 4.00),
    "us.anthropic.claude-opus-4-6-v1": (15.00, 75.00),
    "us.anthropic.claude-opus-4-5-20251101-v1:0": (15.00, 75.00),
}


@dataclass
class CallRecord:
    """Single API call record."""
    model: str
    role: str  # "generator", "judge", "clerk", "reflect"
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def estimated_cost(self) -> float:
        # Use CLI-reported cost for agent calls if available
        if hasattr(self, "_agent_cost"):
            return self._agent_cost
        pricing = PRICING.get(self.model)
        if not pricing:
            return 0.0
        input_cost = (self.input_tokens / 1_000_000) * pricing[0]
        output_cost = (self.output_tokens / 1_000_000) * pricing[1]
        return input_cost + output_cost


@dataclass
class UsageTracker:
    """Accumulates token usage across a simmer run."""
    calls: list[CallRecord] = field(default_factory=list)

    def record(self, model: str, role: str, response) -> None:
        """Record usage from an Anthropic API response."""
        if hasattr(response, "usage") and response.usage:
            self.calls.append(CallRecord(
                model=model,
                role=role,
                input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
                output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
            ))

    def record_tokens(self, model: str, role: str, input_tokens: int, output_tokens: int) -> None:
        """Record usage directly from token counts."""
        self.calls.append(CallRecord(
            model=model, role=role,
            input_tokens=input_tokens, output_tokens=output_tokens,
        ))

    def record_agent(self, model: str, role: str, result_message) -> None:
        """Record usage from a Claude Agent SDK ResultMessage.

        The ResultMessage.usage dict only has the final turn's tokens,
        but total_cost_usd aggregates the entire multi-turn session.
        We store both — tokens are approximate, cost is accurate.
        """
        usage = getattr(result_message, "usage", None) or {}
        cost = getattr(result_message, "total_cost_usd", None)
        record = CallRecord(
            model=model, role=role,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )
        # Override estimated cost with the CLI's reported cost if available
        if cost is not None:
            record._agent_cost = cost  # type: ignore[attr-defined]
        self.calls.append(record)

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost(self) -> float:
        return sum(c.estimated_cost for c in self.calls)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def by_role(self) -> dict[str, dict]:
        """Breakdown by role."""
        roles: dict[str, dict] = {}
        for c in self.calls:
            if c.role not in roles:
                roles[c.role] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}
            roles[c.role]["calls"] += 1
            roles[c.role]["input_tokens"] += c.input_tokens
            roles[c.role]["output_tokens"] += c.output_tokens
            roles[c.role]["cost"] += c.estimated_cost
        return roles

    def by_model(self) -> dict[str, dict]:
        """Breakdown by model."""
        models: dict[str, dict] = {}
        for c in self.calls:
            if c.model not in models:
                models[c.model] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}
            models[c.model]["calls"] += 1
            models[c.model]["input_tokens"] += c.input_tokens
            models[c.model]["output_tokens"] += c.output_tokens
            models[c.model]["cost"] += c.estimated_cost
        return models

    def summary(self) -> str:
        """Human-readable cost summary."""
        lines = ["Run cost breakdown:"]
        for role, data in sorted(self.by_role().items()):
            lines.append(
                f"  {role:12s}: {data['calls']:2d} calls, "
                f"{data['input_tokens']:,} in / {data['output_tokens']:,} out "
                f"= ${data['cost']:.4f}"
            )
        lines.append(f"  {'Total':12s}: {self.call_count} calls, "
                      f"{self.total_tokens:,} tokens = ${self.total_cost:.4f}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serializable summary."""
        return {
            "total_calls": self.call_count,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.total_cost, 6),
            "by_role": self.by_role(),
            "by_model": self.by_model(),
        }
