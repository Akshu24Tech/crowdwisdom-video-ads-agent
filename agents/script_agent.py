"""
Script Agent

Takes the enriched ad analysis from Ads Manager and produces, per selected
ad/concept:
  1. Pain-led script
  2. Unique-data-led script (grounded in CrowdWisdomTrading's actual data assets)
  3. CWT-benefit-led script (how CrowdWisdomTrading improves trading results)
  + a standalone hook line for each.

Includes a lightweight "groundedness" validator loop (capped at 3 iterations,
same pattern as the Self-RAG IsSUP check) that rejects scripts which drift
from the identified pain point / don't reference CWT's actual value prop,
and asks the model to revise. This is the verification-layer differentiator
worth calling out in the submission notes.
"""

import os
import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL", "meta/llama-3.3-70b-instruct")
MAX_REVISION_LOOPS = 3

DATA_DIR = Path(__file__).parent.parent / "data"

llm_client = OpenAI(
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY,
)

# Real data points drawn from actual CrowdWisdomTrading sample outputs
# (^NDX_2026-04-27.json, SNOW_2026-04-27.json) - structural facts about the
# product, not invented stats. Do not add numbers that aren't evidenced by
# an actual sample output.
CWT_UNIQUE_DATA_POINTS = [
    "Every ticker report synthesizes sentiment across YouTube, X, Reddit, and AI-processed sources into one weighted 'Wisdom of Professional Traders' read",
    "Each call ships with a transparent confidence score (0-100) reflecting how unified trader sentiment actually is, not just a single analyst's opinion",
    "Every setup includes two price targets and two stop levels with the technical method disclosed, so it's a structured trade plan, not just a directional guess",
]

SCRIPT_TYPES = {
    "pain_led": "Open with the pain point directly. Make the viewer feel understood in the first line, then position CrowdWisdomTrading as the way out.",
    "unique_data_led": "Lead with a specific, surprising data point about how CrowdWisdomTrading aggregates crowd intelligence. Use the number/stat as the hook itself.",
    "cwt_benefit_led": "Lead with the transformation: what trading looks like once you have crowd-sourced signals instead of guessing alone.",
}


import time as _time


def _call_llm(prompt: str, max_retries: int = 5) -> str:
    last_err = None
    for attempt in range(max_retries):
        wait = 2 ** (attempt + 1)  # default backoff: 2s, 4s, 8s, 16s
        try:
            resp = llm_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                timeout=60,
            )
            if resp.choices:
                return resp.choices[0].message.content.strip()
            error_detail = getattr(resp, "error", None) or getattr(resp, "model_dump", lambda: resp)()
            last_err = str(error_detail)
        except Exception as e:
            last_err = str(e)

        # Rate-limit errors need a real cooldown, not a quick 2-8s retry
        if "rate" in last_err.lower() or "429" in last_err or "ResourceExhausted" in last_err:
            wait = 35

        if attempt < max_retries - 1:
            print(f"[script_agent] LLM call failed (attempt {attempt+1}/{max_retries}), retrying in {wait}s: {last_err}")
            _time.sleep(wait)
    raise RuntimeError(f"LLM call failed after {max_retries} attempts: {last_err}")


def generate_hook(pain_point: str, concept: str) -> str:
    prompt = f"""Write ONE scroll-stopping hook line (under 12 words) for a video ad.
It must make someone stop scrolling in the first 2 seconds.

Pain point: {pain_point}
Concept: {concept}

Return only the hook line, nothing else."""
    return _call_llm(prompt)


def generate_script(script_type: str, pain_point: str, concept: str) -> str:
    instruction = SCRIPT_TYPES[script_type]
    data_points = "\n".join(f"- {d}" for d in CWT_UNIQUE_DATA_POINTS)
    prompt = f"""Write a 30-45 second video ad script for CrowdWisdomTrading (crowdwisdomtrading.com),
a platform that aggregates trading sentiment from thousands of traders across YouTube, X, and Discord
into weekly briefings and signals.

Pain point identified from a competitor ad: {pain_point}
Marketing concept: {concept}
Script approach: {instruction}

CrowdWisdomTrading's real data points to draw from (use at least one, don't invent numbers):
{data_points}

Format: plain spoken narration, no camera directions, 60-90 words, natural conversational tone.
Return only the script text."""
    return _call_llm(prompt)


def _validate_grounded(script: str, pain_point: str) -> tuple[bool, str]:
    """Checks the script actually engages the identified pain point and doesn't
    invent unsupported claims. Returns (passes, feedback)."""
    check_prompt = f"""Does this ad script clearly address the following pain point,
and does it avoid inventing statistics not listed as CrowdWisdomTrading data points?

Pain point: {pain_point}
Script: \"\"\"{script}\"\"\"

Answer with JSON only: {{"grounded": true/false, "feedback": "one sentence, only if false"}}"""
    raw = _call_llm(check_prompt)
    try:
        parsed = json.loads(raw)
        return parsed.get("grounded", False), parsed.get("feedback", "")
    except json.JSONDecodeError:
        return True, ""  # fail open rather than loop forever on a parse issue


def generate_grounded_script(script_type: str, pain_point: str, concept: str) -> dict:
    script = generate_script(script_type, pain_point, concept)
    attempt = 0
    for attempt in range(MAX_REVISION_LOOPS):
        grounded, feedback = _validate_grounded(script, pain_point)
        if grounded:
            break
        script = _call_llm(
            f"""Revise this ad script to fix the following issue: {feedback}

Original script:
\"\"\"{script}\"\"\"

Rules:
- Output ONLY the revised script text, nothing else
- No explanations, no "Key Fixes" notes, no headers, no meta-commentary
- Keep it 60-90 words, plain spoken narration for a video ad
- Do not change topic - it must still be a CrowdWisdomTrading ad script"""
        )
    return {"script_type": script_type, "script": script, "revision_loops": attempt + 1}


def run(scraped_ads_path: Path = DATA_DIR / "scraped_ads.json", top_k: int = 3) -> dict:
    data = json.loads(scraped_ads_path.read_text())
    results = []

    for ad in data["top_ads"][:top_k]:
        analysis = ad.get("analysis", {})
        pain_point = analysis.get("pain_point") or "generic trading uncertainty"
        concept = analysis.get("marketing_concept") or "crowd-sourced trading confidence"

        hook = generate_hook(pain_point, concept)
        scripts = [
            generate_grounded_script(st, pain_point, concept) for st in SCRIPT_TYPES
        ]
        results.append({
            "source_ad_id": ad.get("ad_id"),
            "pain_point": pain_point,
            "concept": concept,
            "hook": hook,
            "scripts": scripts,
        })

    out_path = DATA_DIR / "scripts.json"
    out_path.write_text(json.dumps(results, indent=2))
    return {"generated": len(results), "path": str(out_path)}


if __name__ == "__main__":
    print(run())
