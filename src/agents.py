"""Two incentive-opposed LLM personas. Each returns a structured JSON proposal;
no code execution or tool-calling happens inside this module -- that's ep_bridge/
mcp_server's job. This module only talks to the LLM and parses its answer."""
import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PERSONA_PROMPTS = {
    "energy": (
        "You are the Energy Advocate for a building HVAC control system. Your sole goal is "
        "minimizing electricity consumption and cost, especially during high grid-carbon-intensity "
        "hours. You will be given the current setpoints and the last measured zone conditions for "
        "one time-of-day block. Propose new heating and cooling setpoints (Celsius) that reduce "
        "energy use. You do not have the final say -- a separate Comfort Advocate and a judge will "
        "weigh in -- so make your case, but do not propose setpoints outside 14-32C.\n\n"
        "Respond with ONLY a JSON object, no other text: "
        '{"heating_setpoint_c": <float>, "cooling_setpoint_c": <float>, "rationale": "<one sentence>"}'
    ),
    "comfort": (
        "You are the Comfort Advocate for a building HVAC control system. Your sole goal is "
        "protecting occupant thermal comfort (PMV close to 0, i.e. thermally neutral). You will be "
        "given the current setpoints and the last measured zone conditions for one time-of-day block. "
        "Propose new heating and cooling setpoints (Celsius) that keep or restore comfort. You do not "
        "have the final say -- a separate Energy Advocate and a judge will weigh in -- so make your "
        "case, but do not propose setpoints outside 14-32C.\n\n"
        "Respond with ONLY a JSON object, no other text: "
        '{"heating_setpoint_c": <float>, "cooling_setpoint_c": <float>, "rationale": "<one sentence>"}'
    ),
    "repair": (
        "You are the Repair Agent for a building HVAC control system. The setpoints you were "
        "just given caused EnergyPlus to fail with a severe or fatal simulation error. You will be "
        "given the setpoints that failed and the exact error text. Propose corrected heating and "
        "cooling setpoints (Celsius) for the same time block that are more likely to run "
        "successfully -- stay within a conservative 18-26C range unless the error clearly indicates "
        "a different problem.\n\n"
        "Respond with ONLY a JSON object, no other text: "
        '{"heating_setpoint_c": <float>, "cooling_setpoint_c": <float>, "rationale": "<one sentence>"}'
    ),
}


def build_client() -> OpenAI:
    return OpenAI(
        api_key=os.environ["GROQ_API_KEY"],
        base_url=os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
    )


def _extract_json(raw_text: str) -> dict:
    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object found in LLM response: {raw_text!r}")
    return json.loads(match.group(0))


def propose(persona: str, client, model: str, context: dict) -> dict:
    if persona not in PERSONA_PROMPTS:
        raise ValueError(f"unknown persona: {persona}")

    user_message = (
        f"Time block: {context['hour_block']}\n"
        f"Current heating setpoint: {context['current_heating_setpoint_c']}C\n"
        f"Current cooling setpoint: {context['current_cooling_setpoint_c']}C\n"
        f"Last measured avg zone temp: {context['avg_zone_temp_c']}C\n"
        f"Last measured avg zone RH: {context['avg_zone_rh_pct']}%\n"
        f"Last measured avg PMV: {context['avg_pmv']}\n"
        f"Energy used this block: {context['kwh_this_block']} kWh\n"
        f"Grid carbon intensity level: {context['carbon_level']}"
    )

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": PERSONA_PROMPTS[persona]},
            {"role": "user", "content": user_message},
        ],
    )
    raw_text = response.choices[0].message.content

    try:
        parsed = _extract_json(raw_text)
        heating = float(parsed["heating_setpoint_c"])
        cooling = float(parsed["cooling_setpoint_c"])
        rationale = str(parsed["rationale"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"malformed proposal from {persona} agent: {raw_text!r}") from exc

    return {
        "agent": persona,
        "heating_setpoint_c": heating,
        "cooling_setpoint_c": cooling,
        "rationale": rationale,
    }


def propose_repair(client, model: str, block_name: str, failed_setpoints: dict, error_text: str) -> dict:
    user_message = (
        f"Time block: {block_name}\n"
        f"Failed heating setpoint: {failed_setpoints['heating_setpoint_c']}C\n"
        f"Failed cooling setpoint: {failed_setpoints['cooling_setpoint_c']}C\n"
        f"EnergyPlus error:\n{error_text}"
    )

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": PERSONA_PROMPTS["repair"]},
            {"role": "user", "content": user_message},
        ],
    )
    raw_text = response.choices[0].message.content

    try:
        parsed = _extract_json(raw_text)
        heating = float(parsed["heating_setpoint_c"])
        cooling = float(parsed["cooling_setpoint_c"])
        rationale = str(parsed["rationale"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"malformed repair proposal: {raw_text!r}") from exc

    return {
        "agent": "repair",
        "heating_setpoint_c": heating,
        "cooling_setpoint_c": cooling,
        "rationale": rationale,
    }
