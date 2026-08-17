from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import contribution_eye

ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "template.md"
SVG_TEMPLATE_PATH = ROOT / "terminal_template.svg"
OUTPUT_PATH = ROOT / "README.md"
SVG_OUTPUT_PATH = ROOT / "assets" / "terminal.svg"
EYE_OUTPUT_PATH = ROOT / "assets" / "contribution-eye.svg"
CACHE_PATH = ROOT / ".stats_cache.json"

LINKEDIN_HANDLE = "samuel-gomez-piamba"
INSTAGRAM_HANDLE = "sd_gomezp"
EMAIL = "sgdotdev@gmail.com"
LINKEDIN_URL = f"https://www.linkedin.com/in/{LINKEDIN_HANDLE}/"
INSTAGRAM_URL = f"https://www.instagram.com/{INSTAGRAM_HANDLE}"


def github_get(url: str, token: str | None = None, accept: str = "application/vnd.github+json") -> dict:
    headers = {
        "Accept": accept,
        "User-Agent": "profile-readme-updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_all_repos(username: str, token: str | None) -> list[dict]:
    repos: list[dict] = []
    page = 1

    while True:
        query = urllib.parse.urlencode(
            {
                "per_page": 100,
                "page": page,
                "type": "owner",
                "sort": "updated",
            }
        )
        url = f"https://api.github.com/users/{username}/repos?{query}"
        chunk = github_get(url, token)
        if not chunk:
            break
        repos.extend(chunk)
        if len(chunk) < 100:
            break
        page += 1

    return repos


def get_total_stars(username: str, token: str | None) -> int:
    repos = get_all_repos(username, token)
    return sum(repo.get("stargazers_count", 0) for repo in repos)


def get_commit_count(username: str, token: str | None) -> int:
    query = urllib.parse.urlencode({"q": f"author:{username}", "per_page": 1})
    url = f"https://api.github.com/search/commits?{query}"

    data = github_get(
        url,
        token,
        accept="application/vnd.github.cloak-preview+json",
    )
    return int(data.get("total_count", 0))


def get_user_stats(username: str, token: str | None) -> dict[str, int]:
    user = github_get(f"https://api.github.com/users/{username}", token)

    return {
        "REPOS": int(user.get("public_repos", 0)),
        "FOLLOWERS": int(user.get("followers", 0)),
        "STARS": get_total_stars(username, token),
        "COMMITS": get_commit_count(username, token),
    }


CONTRIBUTION_CALENDAR_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays {
            weekday
            contributionCount
          }
        }
      }
    }
  }
}
"""

# GitHub's GraphQL `color` field returns light-theme hex codes (#ebedf0 etc.)
# regardless of profile theme, which clash with this profile's dark terminal
# aesthetic. Bucket on the raw count instead and map to our own dark palette.
DARK_GREEN_LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


def _level_color(count: int) -> str:
    if count == 0:
        return DARK_GREEN_LEVELS[0]
    if count <= 2:
        return DARK_GREEN_LEVELS[1]
    if count <= 5:
        return DARK_GREEN_LEVELS[2]
    if count <= 9:
        return DARK_GREEN_LEVELS[3]
    return DARK_GREEN_LEVELS[4]


def get_contribution_calendar(username: str, token: str) -> tuple[dict[str, str], int]:
    """Fetch the real day-by-day contribution calendar. Only available via
    GraphQL with a token that has read:user scope -- the workflow's default
    GITHUB_TOKEN cannot make this query regardless of its permissions block."""
    body = json.dumps({"query": CONTRIBUTION_CALENDAR_QUERY, "variables": {"login": username}}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-updater",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if "errors" in payload:
        raise RuntimeError(f"GitHub GraphQL error: {payload['errors']}")

    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    calendar: dict[str, str] = {}
    for week_idx, week in enumerate(weeks):
        for day in week["contributionDays"]:
            calendar[f"{week_idx}-{day['weekday']}"] = _level_color(day["contributionCount"])

    return calendar, len(weeks)


def load_cached_stats() -> dict | None:
    if not CACHE_PATH.exists():
        return None
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def resolve_date(payload: dict) -> str:
    """Reuse the last recorded date when the payload (stats + contribution
    calendar) hasn't changed, so a run with no real change produces byte-
    identical output and the workflow doesn't commit."""
    cached = load_cached_stats()
    if cached and cached.get("payload") == payload:
        return cached["date"]

    date = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    CACHE_PATH.write_text(json.dumps({"date": date, "payload": payload}, indent=2) + "\n", encoding="utf-8")
    return date


def build_readme(template: str, username: str, stats: dict[str, int], date: str) -> str:
    replacements = {
        "{{USERNAME}}": username,
        "{{DATE}}": date,
        "{{REPOS}}": f"{stats['REPOS']:,}",
        "{{STARS}}": f"{stats['STARS']:,}",
        "{{COMMITS}}": f"{stats['COMMITS']:,}",
        "{{FOLLOWERS}}": f"{stats['FOLLOWERS']:,}",
        "{{LINKEDIN_HANDLE}}": LINKEDIN_HANDLE,
        "{{INSTAGRAM_HANDLE}}": INSTAGRAM_HANDLE,
        "{{LINKEDIN_URL}}": LINKEDIN_URL,
        "{{INSTAGRAM_URL}}": INSTAGRAM_URL,
        "{{EMAIL}}": EMAIL,
    }

    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result


def main() -> None:
    username = os.getenv("GITHUB_USERNAME") or os.getenv("GITHUB_ACTOR")
    if not username:
        raise RuntimeError("Missing GITHUB_USERNAME (or GITHUB_ACTOR) environment variable.")

    token = os.getenv("GITHUB_TOKEN")

    contrib_token = os.getenv("CONTRIB_TOKEN")
    if not contrib_token:
        raise RuntimeError(
            "Missing CONTRIB_TOKEN environment variable "
            "(needs a classic PAT with read:user scope to read the contribution calendar)."
        )

    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
    if not SVG_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"SVG template not found: {SVG_TEMPLATE_PATH}")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    svg_template = SVG_TEMPLATE_PATH.read_text(encoding="utf-8")

    try:
        stats = get_user_stats(username, token)
        calendar, weeks = get_contribution_calendar(username, contrib_token)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error ({exc.code}): {body}") from exc

    date = resolve_date({"stats": stats, "calendar": calendar})
    rendered_readme = build_readme(template, username, stats, date)
    rendered_svg = build_readme(svg_template, username, stats, date)

    calendar_grid = {tuple(int(part) for part in key.split("-")): color for key, color in calendar.items()}
    eye_svg = contribution_eye.render_svg(calendar_grid, weeks, 7)

    OUTPUT_PATH.write_text(rendered_readme, encoding="utf-8")
    SVG_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_OUTPUT_PATH.write_text(rendered_svg, encoding="utf-8")
    EYE_OUTPUT_PATH.write_text(eye_svg, encoding="utf-8")

    print("README.md, assets/terminal.svg, and assets/contribution-eye.svg updated successfully")


if __name__ == "__main__":
    main()
