from src.utils.suggestion_dedupe import (
    dedupe_prompts,
    grounded_in_reasoning,
    normalize_search_prompt,
)


def test_normalize_caps_at_eight_words():
    q = normalize_search_prompt(
        "red UPS truck blocking the bike lane while turning left onto Broadway",
        max_words=8,
    )
    assert len(q.split()) <= 8


def test_grounded_accepts_rephrase():
    reasoning = (
        "A red UPS delivery truck is blocking the bike lane and appears about "
        "to turn left onto Broadway."
    )
    assert grounded_in_reasoning("red UPS truck blocking bike lane", reasoning)


def test_grounded_rejects_invention():
    reasoning = "A cyclist rides past a parked sedan on a sunny street."
    assert not grounded_in_reasoning("UPS truck blocking bike lane", reasoning)


def test_dedupe_prompts_similar_only():
    out = dedupe_prompts(
        [
            "red UPS truck blocking lane",
            "red UPS truck blocking the lane",
            "Cyclist swerving around open door",
        ],
        limit=10,
    )
    assert len(out) == 2
