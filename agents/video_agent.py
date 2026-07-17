"""
Video Agent

IMPORTANT INTEGRATION NOTE (read before wiring this up):
OpenMontage (github.com/calesthio/OpenMontage) is NOT a simple importable
Python library with a render(script) function. It's an *agent-driven* video
production system meant to be operated by an AI coding assistant (Claude
Code, Cursor, etc.) that reads its markdown "director skills" and calls its
~52 tools directly, checkpointing state and asking for human approval at
creative decision points.

That means the realistic integration paths are:

  OPTION A (closest to spec, more setup): Have Hermes's Video Agent shell
  out to OpenMontage's CLI entrypoint, passing our script/hook as a brief.
  Before wiring this, `git clone` OpenMontage, read AGENT_GUIDE.md and
  README.md for the actual CLI command and expected brief format (these
  may differ from the placeholder below - verify against the real repo).

  OPTION B (pragmatic fallback, recommended if Option A eats too much of
  your timeline): Use Remotion directly (remotion.dev) - it's a mature,
  well-documented, purely programmatic React-based video renderer. You
  write a React composition, pass in script/hook/data as props, and run
  `npx remotion render` headlessly. No agentic layer to fight with.

This file implements Option A as the primary path with a clean subprocess
boundary, and falls back to Option B if OpenMontage isn't configured in
the environment. Ship whichever one actually works for you - the brief
asks for "a 30-60 sec ad generated based on the script," not a specific
tool at all costs.
"""

import os
import json
import subprocess
import platform
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUTS_DIR = DATA_DIR / "outputs"

OPENMONTAGE_REPO_PATH = os.environ.get("OPENMONTAGE_REPO_PATH")  # set once cloned locally
REMOTION_PROJECT_PATH = os.environ.get("REMOTION_PROJECT_PATH")  # set if using fallback


def _write_brief(script_entry: dict) -> Path:
    """Writes a job brief file that either pipeline can consume."""
    brief = {
        "title": f"cwt-ad-{script_entry.get('source_ad_id', 'x')}",
        "hook": script_entry["hook"],
        "script": script_entry["scripts"][0]["script"],  # pick primary variant; loop externally for all 3
        "duration_target_seconds": 45,
        "brand": "CrowdWisdomTrading",
        "cta": "Get your free weekly crowd sentiment briefing at crowdwisdomtrading.com",
    }
    brief_path = DATA_DIR / f"brief_{brief['title']}.json"
    brief_path.write_text(json.dumps(brief, indent=2))
    return brief_path


def render_with_openmontage(brief_path: Path) -> dict:
    """Shells out to OpenMontage. Verify the actual command against
    AGENT_GUIDE.md / README.md in the cloned repo - this is a best-guess
    placeholder for a CLI invocation pattern, not confirmed syntax."""
    if not OPENMONTAGE_REPO_PATH:
        raise RuntimeError("OPENMONTAGE_REPO_PATH not set - skipping to fallback")

    out_name = brief_path.stem + ".mp4"
    out_path = OUTPUTS_DIR / out_name

    cmd = [
        "python", "-m", "openmontage.cli", "run",
        "--brief", str(brief_path),
        "--output", str(out_path),
    ]
    result = subprocess.run(
        cmd, cwd=OPENMONTAGE_REPO_PATH, capture_output=True, text=True, timeout=1800
    )
    if result.returncode != 0:
        raise RuntimeError(f"OpenMontage render failed: {result.stderr[-2000:]}")

    return {"engine": "openmontage", "output_path": str(out_path)}


def render_with_remotion_fallback(brief_path: Path) -> dict:
    """Fallback: assumes a Remotion project already scaffolded with a
    composition that accepts these props (see README for the minimal
    composition template)."""
    if not REMOTION_PROJECT_PATH:
        raise RuntimeError("Neither OPENMONTAGE_REPO_PATH nor REMOTION_PROJECT_PATH set")

    brief = json.loads(brief_path.read_text())
    out_name = brief_path.stem + ".mp4"
    out_path = OUTPUTS_DIR / out_name

    cmd = [
        "npx", "remotion", "render", "CWTAd", str(out_path),
        f"--props={brief_path}",
    ]
    result = subprocess.run(
        cmd, cwd=REMOTION_PROJECT_PATH, capture_output=True, text=True, timeout=1800,
        shell=(platform.system() == "Windows"),
    )
    if result.returncode != 0:
        raise RuntimeError(f"Remotion render failed: {result.stderr[-2000:]}")

    return {"engine": "remotion", "output_path": str(out_path)}


def run(scripts_path: Path = DATA_DIR / "scripts.json", top_k: int = 1) -> list[dict]:
    scripts = json.loads(scripts_path.read_text())
    results = []
    for entry in scripts[:top_k]:
        brief_path = _write_brief(entry)
        try:
            render_result = render_with_openmontage(brief_path)
        except Exception as e:
            print(f"[video_agent] OpenMontage path failed/unset ({e}), trying Remotion fallback")
            render_result = render_with_remotion_fallback(brief_path)
        render_result["brief"] = str(brief_path)
        render_result["generated_at"] = datetime.utcnow().isoformat()
        results.append(render_result)

    manifest_path = DATA_DIR / "video_outputs.json"
    manifest_path.write_text(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    print(run())