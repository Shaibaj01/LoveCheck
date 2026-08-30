import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.event_dedupe import (  # noqa: E402
    dedupe_key_events,
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
    assert grounded_in_reasoning("UPS truck turning left Broadway", reasoning)


def test_grounded_rejects_invention():
    reasoning = "A cyclist rides past a parked sedan on a sunny street."
    assert not grounded_in_reasoning("UPS truck blocking bike lane", reasoning)
    assert not grounded_in_reasoning("jaywalking near-miss with taxi", reasoning)


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


def test_dedupe_key_events_same_slot():
    events = [
        {
            "query_text": "red truck blocking bike lane",
            "label": "Blocked Lane",
            "original_video": "a.mp4",
            "segment_start_sec": 10,
        },
        {
            "query_text": "red truck blocking bike lane",
            "label": "Blocked Lane Again",
            "original_video": "a.mp4",
            "segment_start_sec": 10,
        },
        {
            "query_text": "cyclist past open car door",
            "label": "Open Door",
            "original_video": "b.mp4",
            "segment_start_sec": 40,
        },
    ]
    out = dedupe_key_events(events)
    assert len(out) == 2
