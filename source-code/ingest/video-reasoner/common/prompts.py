"""
Preconfigured prompts for different video analysis scenarios.
Set the 'scenario' key in your secret to switch between them.
All scenario prompts request structured JSON output (see structured_output.py).
"""

from .structured_output import wrap_prompt_with_structured_output

SCENARIO_PROMPTS = {
    "surveillance": """Analyze this surveillance footage. Focus on people, unusual behavior, safety hazards, abandoned objects, vehicles, crowds, and security concerns. Be specific about locations within the frame.""",

    "traffic": """Analyze this traffic camera footage. Focus on vehicles, traffic flow, violations, pedestrians, congestion, accidents or near-misses, and road conditions.""",

    "nhl": """Analyze this NHL hockey game footage. Focus on key plays, player actions, penalties, goaltending, special teams, face-offs, and team formations. Note jersey numbers and team colors when visible.""",

    "sports": """Analyze this sports footage. Focus on key plays, player movement, scoring chances, defense, fouls, momentum shifts, and notable performances.""",

    "retail": """Analyze this retail store footage. Focus on customer flow, product interactions, checkout queues, staff activity, suspicious behavior, and store layout usage.""",

    "warehouse": """Analyze this warehouse footage. Focus on forklifts, workers, inventory handling, PPE compliance, hazards, spills, and dock activity.""",

    "egocentric": """Analyze this first-person (egocentric) footage. Focus on hand actions, object manipulation, tools, task steps, and workspace context from the wearer's viewpoint.""",

    "general": """Analyze this video footage. Focus on people, objects, environment, notable activities, and interactions. Be factual and specific.""",

    "nyc_control": """Analyze this NYC urban footage for command and control. Focus on location cues, readable signage or plates, traffic or public-safety anomalies, vehicles of interest, and whether the scene appears controlled or needs monitoring.""",
}


DEFAULT_SCENARIO = "general"


def get_prompt_for_scenario(scenario: str) -> str:
    """
    Get the scenario prompt with structured JSON output instructions.
    Falls back to 'general' if scenario is not found.
    """
    scenario_lower = scenario.lower().strip()

    if scenario_lower in SCENARIO_PROMPTS:
        base = SCENARIO_PROMPTS[scenario_lower]
    else:
        import logging
        logging.warning(f"[PROMPTS] Unknown scenario '{scenario}', falling back to 'general'")
        base = SCENARIO_PROMPTS["general"]

    return wrap_prompt_with_structured_output(base)


def get_available_scenarios() -> list[str]:
    """Return list of all available scenario keys"""
    return list(SCENARIO_PROMPTS.keys())


PERCEPTION_OBJECT_PROMPT = """List visible objects in this video clip. Respond with JSON only (no markdown):
{
  "summary": "short phrase e.g. 2 people, 1 forklift",
  "detections": [
    {"class": "person", "count": 2, "confidence": 0.9},
    {"class": "forklift", "count": 1, "confidence": 0.85}
  ]
}
Use common COCO-style class names (person, car, truck, forklift, bicycle, dog, etc.).
Only include objects you can clearly see. confidence is 0.0-1.0."""
