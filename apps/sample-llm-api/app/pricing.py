MODEL_PRICING_USD_PER_1M_TOKENS = {
    "gpt-4o-mini-mock": {
        "input": 0.15,
        "output": 0.60,
    },
    "gemma3:1b": {
        "input": 0.0,
        "output": 0.0,
    },
}


def estimate_infra_cost_usd(compute_seconds: float, hourly_usd: float) -> float:
    return round((compute_seconds / 3600) * hourly_usd, 8)


def estimate_tokens(text: str) -> int:
    # Simple demo tokenizer: stable enough for mock observability data.
    return max(1, len(text.split()) * 2)


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING_USD_PER_1M_TOKENS.get(model, {"input": 0.0, "output": 0.0})
    input_cost = input_tokens * pricing["input"] / 1_000_000
    output_cost = output_tokens * pricing["output"] / 1_000_000
    return round(input_cost + output_cost, 8)
