# CrowdWisdomTrading Video Ads Agent

A Hermes-based multi-agent pipeline that scrapes successful Meta ads in a niche,
extracts their marketing psychology, writes three grounded ad scripts for
CrowdWisdomTrading, and renders a 30-45s video ad from the winning script.

Built for the CrowdWisdomTrading Marketing Lead intern assessment.

## Architecture

```
Telegram (via Hermes gateway) -> Hermes (reads skills/crowdwisdom_ad_pipeline.skill.md)
                                       |
                                  MCP server (mcp_server.py)
                                       |
        +------------------------------+------------------------------+
        v                              v                              v
  Ads Manager                   Script Agent                   Video Agent
  (Apify Meta Ad Library        (3 script types + hook,        (Remotion render,
   scrape, LLM pain/            groundedness validator          see "Video
   concept extraction)          loop capped at 3 retries)        rendering" below)
        |                              |                              |
        +--------------------- Kanban board (SQLite) --------------------+
                    TODO -> SCRAPING -> SCRIPTING -> VIDEO -> REVIEW -> DONE
```

`orchestrator.py` also exposes a plain-Python `run_pipeline()` entrypoint so
every stage is independently testable without Hermes running at all.

## Repo layout

```
orchestrator.py            # coordinates all 3 stages + kanban transitions
mcp_server.py               # exposes the 4 pipeline operations as MCP tools for Hermes
agents/
  ads_manager.py             # Apify scrape + ranking + pain/concept extraction
  script_agent.py             # 3 script types + hook + groundedness validator
  video_agent.py               # Remotion render (see video-render/)
kanban/board.py                # SQLite-backed kanban board
skills/crowdwisdom_ad_pipeline.skill.md  # Hermes skill: drives the tool-call loop
telegram_bot.py                 # standalone Telegram fallback (if not using Hermes gateway)
video-render/                    # Remotion project - separate Node/React app that
                                   # renders the actual video (see below)
data/                             # scraped_ads.json, scripts.json, video_outputs.json
```

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows; use `source venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
copy .env.example .env         # then fill in your keys
```

You'll need:
- **Apify token** - use a scoped/free-tier account, not one tied to paid credentials
  (see "Submission checklist" below - this token gets shared for rerunning)
- **An LLM provider key** - this project defaults to **OpenRouter** (see below)
- **A Meta Ad Library scraper actor** - search "Meta Ad Library" or "Facebook Ads
  Scraper" in the Apify store, set its ID as `APIFY_META_ADS_ACTOR` in `.env`
- **Node.js + npm** - required for the Remotion video render step

### LLM provider - OpenRouter (default)

```dotenv
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-v1-xxxxxxxxxxxxx
LLM_MODEL=openrouter/free
```

`openrouter/free` is OpenRouter's auto-router - it picks whichever free model
currently has capacity, instead of pinning to one specific free model that can
get temporarily saturated (this happened repeatedly during development with
`meta-llama/llama-3.3-70b-instruct:free` specifically - the auto-router avoids
that single-point congestion). No payment required.

Both `ads_manager.py` and `script_agent.py` wrap every LLM call in a
retry-with-backoff helper: transient errors get 2s/4s/8s backoff, and
rate-limit errors specifically wait ~35s (matching what OpenRouter's own
`retry_after_seconds` suggests) before retrying, up to 5 attempts.

To switch to NVIDIA's build.nvidia.com instead (also permitted by the brief),
override in `.env`:
```dotenv
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=meta/llama-3.3-70b-instruct
```
Note: during development, `integrate.api.nvidia.com` was unreachable from the
development machine specifically (timed out identically on two different
networks) - this looked like a local network/firewall issue rather than an
NVIDIA-side problem, but wasn't fully root-caused. Test connectivity first
with a minimal request before relying on this path.

## Running it standalone (no Hermes/Telegram needed)

```bash
python orchestrator.py
```

This runs all three stages once with hardcoded search terms
(`trading signals`, `stock alerts`, `day trading community`) and prints the
kanban board state at the end. This is the fastest way to verify the full
chain works end to end - confirmed working: Apify scrape (300 ads found,
top 5 ranked and analyzed) -> Script Agent (3 grounded scripts + hook per ad)
-> Video Agent (Remotion render to an .mp4).

Individual stages can also be run on their own for faster debugging:
```bash
python agents\ads_manager.py     # writes data/scraped_ads.json
python agents\script_agent.py    # reads scraped_ads.json, writes data/scripts.json
python agents\video_agent.py     # reads scripts.json, writes data/video_outputs.json
```

## Video rendering (Remotion)

The brief's preferred tool, OpenMontage, turned out to be agent-driven - it
expects an AI coding assistant reading its skill files and calling its ~52
tools directly, not a plain library `import`/CLI call from another pipeline.
Rather than fight that integration under the timeline, this project uses
**Remotion** (remotion.dev) instead - a mature, purely programmatic,
React-based video renderer. `video_agent.py` still has a documented
OpenMontage code path (`render_with_openmontage`) that's tried first and
falls through to Remotion if `OPENMONTAGE_REPO_PATH` isn't set, so switching
back is a one-line env change if you want to pursue that integration further.

Setup (already done in `video-render/`, included in this repo):
```bash
cd video-render
npm install
npm run dev              # opens Remotion Studio in the browser to preview
```

The composition (`video-render/src/CWTAd.tsx`) takes `hook`, `script`,
`brand`, and `cta` as props and renders a 3-phase 1080x1920 (vertical) video:
hook fades in (0-3s) -> script reveals word-by-word -> CTA fades in for the
last 5s. `video_agent.py` writes each ad's brief to a JSON file and passes it
via `npx remotion render CWTAd <output> --props=<brief.json>`.

Set in `.env`:
```dotenv
REMOTION_PROJECT_PATH=<absolute path to>\crowdwisdom-video-ads-agent\video-render
```

Windows note: `npx` resolves to `npx.cmd` on Windows, which Python's
`subprocess.run()` can't launch directly without `shell=True` - already
handled in `video_agent.py` (auto-detects Windows via `platform.system()`).

`video-render/node_modules/` is gitignored - don't commit it.

## Wiring into Hermes (MCP + skill + Telegram)

Hermes Agent (Nous Research) extends itself two ways: **MCP servers** for new
capabilities, and **markdown skills** (agentskills.io standard) for
workflow/behavior - there's no "register this Python function as a subagent"
API. `mcp_server.py` and `skills/crowdwisdom_ad_pipeline.skill.md` are the
actual integration points, and both are confirmed working end to end.

```powershell
# 1. Install Hermes, pick a free model (Gemini's free tier works well and
#    needs no extra setup if already connected - check `hermes doctor`)
hermes setup
hermes model              # filter/select e.g. gemini-3.1-flash-lite

# 2. Register this project's MCP server - point directly at your venv's
#    python.exe with absolute paths (Hermes launches this as a background
#    process outside your activated shell, so PATH-based `python` lookups
#    can resolve to the wrong interpreter - use the full venv path)
hermes mcp add crowdwisdom-ads --command "<absolute path>\venv\Scripts\python.exe" --args <absolute path>\mcp_server.py
hermes mcp list            # confirm 4 tools show up:
                            # scrape_and_rank_ads, generate_ad_scripts,
                            # render_video_ad, get_kanban_board

# 3. Install the skill - `hermes skills install` only accepts a registry
#    identifier or an HTTP(S) URL, not a local file path, so push this repo
#    to GitHub first and install from the raw URL:
hermes skills install https://raw.githubusercontent.com/<you>/<repo>/main/skills/crowdwisdom_ad_pipeline.skill.md --category custom --name crowdwisdom-ad-pipeline --yes
hermes skills list          # confirm it shows up under "local"/hub-installed

# 4. Telegram gateway
hermes gateway setup        # choose Telegram, paste bot token from @BotFather,
                             # set an allowed user ID (via @userinfobot) so the
                             # bot isn't open to strangers, set home channel
hermes gateway start
```

Once wired, message the bot: **"run the ad pipeline for trading signals"** -
Hermes reads the skill, calls the four MCP tools in order (scrape -> script
-> video -> kanban check), and reports progress back through the same chat.
This is what satisfies "loops and skills" and "telegram" together - one
skill driving a multi-step tool-call loop through real MCP tools, not three
scripts glued together by hand behind a basic bot command.

Confirmed working test (no LLM cost): asking "show me the current kanban
board" correctly triggers `get_kanban_board` via MCP and returns the live
board state in chat.

If MCP/skill wiring isn't available in your environment, `telegram_bot.py`
in this repo is a standalone fallback (`python-telegram-bot`) exposing
`/run`, `/board`, `/approve` directly against the same `orchestrator.py`.

## Groundedness validator (the differentiator)

`script_agent.py` includes a validation loop (capped at 3 iterations) that
checks each generated script actually addresses the identified pain point
and doesn't invent CrowdWisdomTrading stats beyond what's listed in
`CWT_UNIQUE_DATA_POINTS` (which are drawn from real sample outputs -
`^NDX_2026-04-27.json` and `SNOW_2026-04-27.json` - not invented numbers).
The revision prompt is deliberately strict about output format (script text
only, no meta-commentary) after early testing showed looser prompts causing
the model to append explanatory notes or drift off-topic mid-revision.

This isn't required by the brief but demonstrates the reliability/
verification layer this candidate brings to agent pipelines beyond just
"generate and ship."

## Known limitations / honest notes

- **Apify Meta Ad Library scraper actor**: the actor used
  (`automly/facebook-ad-library-scraper`) returns `ad_creative_bodies` as a
  list (an ad can have multiple body variants) and uses `ad_archive_id`, not
  the more generic `ad_creative_body`/`id` field names an earlier version of
  this code assumed - if you swap actors, re-verify field names with a
  one-off `client.actor(...).call()` + print before wiring further.
- **Free-tier LLM rate limits**: `openrouter/free` avoids single-model
  congestion but is still a shared free pool - a full pipeline run costs
  roughly 20-30 LLM calls, which fits comfortably but back-to-back testing
  runs in the same session can occasionally hit a cooldown (handled via
  retry, but expect it to occasionally add ~35s per affected call).
- **Ranking heuristic**: ad "success" is proxied by days-still-running within
  the 30-day window, since Meta Ad Library doesn't expose spend/CTR publicly.

## Submission checklist

- [ ] GitHub repo link
- [ ] Apify token - **use a scoped/free-tier token**, not one tied to any
      paid account or other production credentials
- [ ] Video recording of the kanban board updating live through a full run
      (screen-record `orchestrator.py` running, or the Telegram chat showing
      the pipeline run + kanban state)
- [ ] `.md` output of agent reasoning (`data/scraped_ads.json` +
      `data/scripts.json` formatted into markdown - see the pipeline results
      section, or export via Hermes if running through the gateway)