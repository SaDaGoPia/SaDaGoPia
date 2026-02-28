from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "template.md"
SVG_TEMPLATE_PATH = ROOT / "terminal_template.svg"
OUTPUT_PATH = ROOT / "README.md"
SVG_OUTPUT_PATH = ROOT / "assets" / "terminal.svg"


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


def build_readme(template: str, username: str, stats: dict[str, int]) -> str:
    replacements = {
        "{{USERNAME}}": username,
        "{{DATE}}": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "{{REPOS}}": f"{stats['REPOS']:,}",
        "{{STARS}}": f"{stats['STARS']:,}",
        "{{COMMITS}}": f"{stats['COMMITS']:,}",
        "{{FOLLOWERS}}": f"{stats['FOLLOWERS']:,}",
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

    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
    if not SVG_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"SVG template not found: {SVG_TEMPLATE_PATH}")

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    svg_template = SVG_TEMPLATE_PATH.read_text(encoding="utf-8")

    try:
        stats = get_user_stats(username, token)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error ({exc.code}): {body}") from exc

    rendered_readme = build_readme(template, username, stats)
    rendered_svg = build_readme(svg_template, username, stats)

    OUTPUT_PATH.write_text(rendered_readme, encoding="utf-8")
    SVG_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SVG_OUTPUT_PATH.write_text(rendered_svg, encoding="utf-8")

    print("README.md and assets/terminal.svg updated successfully")


if __name__ == "__main__":
    main()
