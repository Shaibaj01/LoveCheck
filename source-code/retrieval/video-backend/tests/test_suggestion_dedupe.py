from src.utils.suggestion_dedupe import dedupe_prompts


def test_read_path_dedupes_near_landmark_spam():
    prompts = [
        "Food trucks near crosswalk",
        "Food trucks near traffic lights",
        "Cyclist running red light",
    ]
    out = dedupe_prompts(prompts, limit=10)
    assert len(out) == 1
    assert "Cyclist" in out[0]
