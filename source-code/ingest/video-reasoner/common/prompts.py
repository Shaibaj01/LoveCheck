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

    "nyc_safety_surveillance": """You are analyzing a ~5 second clip from NYC real-time public-safety / street surveillance (fixed or slow-pan camera). Output structured JSON only (schema appended below).

Goal: maximize searchable, factual detail for later queries (pedestrians, vehicles, brands, signs, colors, conflicts, hazards). Describe ONLY what is clearly visible in this clip—never guess borough, intent, or text you cannot read.

scene_summary: One sentence—intersection or block context, time-of-day/lighting, dominant activity.

objects (REQUIRED—separate entry per distinct type; use numeric count; notes ≤15 words each):
• People: pedestrians, cyclists, vendors, officers, workers, performers—note approximate count, upper/lower clothing colors, hats, bags, uniforms, costumes.
• Vehicles: cars, taxis, buses, trucks, vans, delivery vehicles, motorcycles, bikes—color, type, direction, stopped vs moving. Logos/brands on trucks, vans, buses, storefronts when readable (e.g. UPS, FedEx, MTA, Verizon, Chase).
• Signage: street signs, avenue/street names, building numbers, one-way/do-not-enter, speed limits, store names, billboards, construction signs—transcribe readable text exactly.
• Street furniture: traffic lights (color if visible), crosswalks, barriers, cones, scaffolding, newsstands, subway entrances, bollards, planters.
• Other: animals, carts, luggage, packages, weapons (only if clearly visible).

actions (REQUIRED): Who is doing what—walking, crossing, waiting at curb, running, gesturing, filming, loading/unloading, turning, idling, honking implied by context, vendor serving, crowd gathering.

events: Scene-level observations—heavy foot traffic, jaywalking, near-miss, double-parked vehicle blocking lane, cyclist on sidewalk, tourist filming, construction activity, blocked crosswalk, vehicle-pedestrian proximity, parade/costume activity. Set severity low/medium/high when a plausible safety concern is visible.

hazards: Concrete visible risks—blocked egress, vehicle in crosswalk, wrong-way movement, person in travel lane, missing cone/barrier, aggressive proximity. [] if none.

attributes: setting (e.g. midtown intersection, commercial corridor), lighting (day/night/dusk), weather if visible, camera motion (static/pan/zoom).

Prioritize: readable text on signs and vehicles, clothing colors, vehicle make/type/color, pedestrian vs vehicle interactions, and anything relevant to NYC street safety monitoring.""",
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
