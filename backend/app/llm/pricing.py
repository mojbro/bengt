# Prices are USD per MILLION tokens, as (input, output).
# Keep this table in sync when adding models. Unknown models return None —
# callers should treat "unknown cost" as non-fatal (don't block the call,
# just skip budget accounting until we price it).
_PRICING: dict[tuple[str, str], tuple[float, float]] = {
    ("openai", "gpt-4o"): (2.50, 10.00),
    ("openai", "gpt-4o-mini"): (0.15, 0.60),
    ("openai", "gpt-4-turbo"): (10.00, 30.00),
}


def estimate_cost(
    provider: str, model: str, input_tokens: int, output_tokens: int
) -> float | None:
    entry = _PRICING.get((provider, model))
    if entry is None:
        return None
    input_price, output_price = entry
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
