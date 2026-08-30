"""
Preconfigured prompts for different video analysis scenarios.
Set the 'scenario' key in your secret to switch between them.

GUI labels & capture types: source-code/shared/ingest_metadata.py (exposed via GET /api/v1/metadata/ingest-config)
"""

SCENARIO_PROMPTS = {
    "surveillance": """Analyze this surveillance footage. Focus on people, unusual behavior, safety hazards, abandoned objects, vehicles, crowds, and security concerns. Be specific about locations within the frame.""",

    "traffic": """Analyze this traffic camera footage. Focus on vehicles, traffic flow, violations, pedestrians, congestion, accidents or near-misses, and road conditions.""",

    "live_driving": """Analyze this ~5 second dashcam or mobile road camera clip. Describe road type, traffic controls, vehicles (especially trucks and buses), pedestrians or cyclists, lane-blocking vehicles, readable signage, and any visible violations or hazards. Describe only what is clearly visible.""",

    "nhl": """Analyze this NHL hockey game footage. Focus on key plays, player actions, penalties, goaltending, special teams, face-offs, and team formations. Note jersey numbers and team colors when visible.""",

    "sports": """Analyze this sports footage. Focus on key plays, player movement, scoring chances, defense, fouls, momentum shifts, and notable performances.""",

    "retail": """Analyze this retail store footage. Focus on customer flow, product interactions, checkout queues, staff activity, suspicious behavior, and store layout usage.""",

    "warehouse": """Analyze this warehouse footage. Focus on forklifts, workers, inventory handling, PPE compliance, hazards, spills, and dock activity.""",

    "egocentric": """Analyze this first-person (egocentric) footage. Focus on hand actions, object manipulation, tools, task steps, and workspace context from the wearer's viewpoint.""",

    "general": """Analyze this video footage. Focus on people, objects, environment, notable activities, and interactions. Be factual and specific.""",

    "nyc_control": """Analyze this NYC urban footage for command and control. Focus on location cues, readable signage or plates, traffic or public-safety anomalies, vehicles of interest, and whether the scene appears controlled or needs monitoring.""",

    "nyc_safety_surveillance": """Analyze this ~5 second NYC street surveillance clip. Describe pedestrians, vehicles, readable signs and vehicle brands, street furniture, crowd activity, and any visible safety concerns. Describe only what is clearly visible.""",
}


DEFAULT_SCENARIO = "general"


def get_prompt_for_scenario(scenario: str) -> str:
    """
    Get the plain scenario prompt.
    Falls back to 'general' if scenario is not found.
    """
    scenario_lower = scenario.lower().strip()

    if scenario_lower in SCENARIO_PROMPTS:
        return SCENARIO_PROMPTS[scenario_lower]

    import logging
    logging.warning(f"[PROMPTS] Unknown scenario '{scenario}', falling back to 'general'")
    return SCENARIO_PROMPTS["general"]


def get_available_scenarios() -> list[str]:
    """Return list of all available scenario keys"""
    return list(SCENARIO_PROMPTS.keys())

