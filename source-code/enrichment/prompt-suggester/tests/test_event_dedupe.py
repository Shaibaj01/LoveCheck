import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from common.event_dedupe import dedupe_key_events, dedupe_prompts  # noqa: E402


USER_EXAMPLES = [
    "Pedestrians waiting at crosswalk",
    "Food cart with ice cream truck",
    "Food trucks near intersection",
    "Yellow taxi passing crosswalk",
    "Food cart near one-way sign",
    "Food cart near fire hydrant",
    "Food trucks near crosswalk",
    "Food trucks near traffic lights",
    "Food trucks near Nathan's Famous",
    "Food trucks near food cart",
]


def test_dedupe_user_food_truck_spam():
    out = dedupe_prompts(USER_EXAMPLES, limit=10)
    assert len(out) == 0


def test_dedupe_keeps_action_prompts():
    prompts = [
        "UPS truck blocking bike lane",
        "Cyclist swerving around open door",
        "Delivery van double parked",
        "Construction fence blocking sidewalk",
    ]
    out = dedupe_prompts(prompts, limit=10)
    assert len(out) == 4


def test_dedupe_key_events_global_food_vendor():
    events = [
        {"query_text": "Food trucks near crosswalk", "label": "Vendors At Crosswalk", "original_video": "a.mp4", "segment_start_sec": 10},
        {"query_text": "Food cart near hydrant", "label": "Cart By Hydrant", "original_video": "b.mp4", "segment_start_sec": 40},
        {"query_text": "UPS truck blocking lane", "label": "Blocked Lane", "original_video": "c.mp4", "segment_start_sec": 20},
    ]
    out = dedupe_key_events(events)
    food = [e for e in out if "food" in e["query_text"].lower() or "cart" in e["query_text"].lower()]
    assert len(food) <= 1
    assert any("UPS" in e["query_text"] for e in out)
