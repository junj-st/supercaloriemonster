import math

from app.schemas import NormalizedFood


def query_weights(query: str) -> tuple[float, float]:
    """(w_generic, w_relevance). Broad (1 token) favors genericness."""
    if len(query.split()) <= 1:
        return (0.6, 0.4)
    return (0.2, 0.8)


def relevance(query: str, name: str, position: int) -> float:
    q = (query or "").strip().lower()
    nm = (name or "").strip().lower()
    if not q or not nm:
        base = 0.0
    elif nm == q:
        base = 1.0
    elif nm.startswith(q):
        base = 0.85
    else:
        q_tokens = q.split()
        n_tokens = set(nm.split())
        if q_tokens and all(t in n_tokens for t in q_tokens):
            base = 0.7
        elif q_tokens:
            base = 0.4 * sum(1 for t in q_tokens if t in n_tokens) / len(q_tokens)
        else:
            base = 0.0
    pos_term = 0.1 / (1 + max(0, position))
    return min(1.0, base + pos_term)


def history_boost(food: NormalizedFood, history: dict) -> float:
    if not history:
        return 0.0
    count = 0
    if food.source_id is not None:
        count = history.get(("id", food.source, food.source_id), 0)
    if count == 0:
        count = history.get(("name", (food.name or "").lower()), 0)
    if count <= 0:
        return 0.0
    return min(0.5, 0.15 * math.log2(1 + count))


def score(food: NormalizedFood, query: str, position: int, history: dict) -> float:
    w_generic, w_relevance = query_weights(query)
    return (
        w_generic * food.generic_score
        + w_relevance * relevance(query, food.name, position)
        + history_boost(food, history)
    )
