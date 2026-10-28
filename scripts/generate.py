#!/usr/bin/env python3
"""Regenerate index.html for the open-source-proof site from live GitHub data.

Data sources (public GitHub REST API):
  - Search API: every PR authored by the user, split into merged-upstream
    and open-under-review sections (PRs in the user's own repos and
    closed-unmerged PRs are excluded).
  - Releases API: latest Sun-Wukhan/terraformer releases.
Local data files:
  - data/notes.json: curated per-PR notes, keyed "owner/repo#number".
    Used when present; otherwise a fallback note is derived from the PR.
  - data/site.json: coverage figures rendered into the Terraformer section.

Auth: uses GITHUB_TOKEN when present (GitHub Actions provides one);
falls back to unauthenticated requests for local runs.
"""

import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from string import Template

USER = "Sun-Wukhan"
API = "https://api.github.com"
ROOT = Path(__file__).resolve().parent.parent


def api_get(path):
    req = urllib.request.Request(
        API + path,
        headers={
            "User-Agent": "open-source-proof-generator",
            "Accept": "application/vnd.github+json",
            **(
                {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}
                if os.environ.get("GITHUB_TOKEN")
                else {}
            ),
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def fmt_date(iso):
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def fetch_authored_prs():
    items = []
    page = 1
    while True:
        q = urllib.parse.quote(f"author:{USER} type:pr")
        data = api_get(f"/search/issues?q={q}&sort=created&order=desc&per_page=100&page={page}")
        items.extend(data["items"])
        if len(data["items"]) < 100:
            return items
        page += 1


def repo_of(item):
    return item["repository_url"].removeprefix(API + "/repos/")


FIXES_RE = re.compile(
    r"(?i)\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\s+"
    r"(?:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#(\d+)|#(\d+))"
)


def fallback_note(item, repo):
    m = FIXES_RE.search(item.get("body") or "")
    if m:
        if m.group(1):
            return f"Fixes {m.group(1)}#{m.group(2)}."
        return f"Fixes issue #{m.group(3)} in {repo}."
    return "Under review."


def build_sections(prs, notes):
    merged, open_prs = [], []
    for item in prs:
        repo = repo_of(item)
        if repo.split("/")[0] == USER:
            continue  # own projects are showcased separately
        pr = item.get("pull_request") or {}
        entry = {
            "repo": repo,
            "number": item["number"],
            "title": item["title"],
            "url": item["html_url"],
            "note": notes.get(f"{repo}#{item['number']}"),
        }
        if item["state"] == "open":
            entry["note"] = entry["note"] or fallback_note(item, repo)
            open_prs.append(entry)
        elif pr.get("merged_at"):
            entry["merged"] = pr["merged_at"]
            merged.append(entry)
        # closed-unmerged PRs are intentionally not showcased
    merged.sort(key=lambda e: e["merged"], reverse=True)
    return merged, open_prs


def merged_item(e):
    meta = f"Merged {fmt_date(e['merged'])}."
    if e["note"]:
        meta += f" {html.escape(e['note'])}"
    return f"""            <li class="merged-item">
              <div class="pr-line">
                <a class="pr-ref" href="{e['url']}">{html.escape(e['repo'])}#{e['number']}</a>
                <span class="pr-title">{html.escape(e['title'])}</span>
                <span class="status status-merged">Merged</span>
              </div>
              <p class="pr-meta">{meta}</p>
            </li>"""


def open_row(e):
    return f"""                <tr>
                  <td class="repo">{html.escape(e['repo'])}</td>
                  <td class="pr"><a href="{e['url']}">#{e['number']}</a></td>
                  <td class="note">{html.escape(e['note'])}</td>
                </tr>"""


def release_item(rel, current):
    tag = html.escape(rel["tag_name"])
    raw_name = rel.get("name") or rel["tag_name"]
    for sep in (" \u2014 ", " - ", ": "):
        if raw_name.startswith(rel["tag_name"] + sep):
            raw_name = raw_name[len(rel["tag_name"] + sep):]
            break
    name = html.escape(raw_name)
    title = f" &mdash; &ldquo;{name}&rdquo;" if raw_name != rel["tag_name"] else ""
    badge = '<span class="tag-current">Current release</span>' if current else ""
    return f"""              <li class="release">
                <div class="release-main">
                  <a class="release-version" href="{rel['html_url']}">{tag}</a>{badge}
                  <span class="release-title">{title}</span>
                </div>
                <div class="release-meta">Published {fmt_date(rel['published_at'])}</div>
              </li>"""


PAGE = Template("""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <meta name="color-scheme" content="light dark" />
    <link rel="icon" href="data:," />
    <title>Navid Khan \u2014 Open Source Proof</title>
    <style>
$css
    </style>
  </head>
  <body>
    <div class="page">
      <header>
        <h1>Navid Khan</h1>
        <div class="handle">
          <svg width="20" height="20" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0c4.42 0 8 3.58 8 8a8.013 8.013 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27-.68 0-1.36.09-2 .27-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8Z"></path></svg>
          <span>GitHub:</span>
          <a href="https://github.com/Sun-Wukhan">Sun-Wukhan</a>
        </div>
      </header>

      <main>
        <section aria-labelledby="terraformer-heading">
          <h2 id="terraformer-heading">Terraformer revival</h2>
          <p class="section-lede">Navid Khan maintains a revival fork of GoogleCloudPlatform/terraformer \u2014 the archived upstream &ldquo;reverse Terraform&rdquo; CLI that generates Terraform files from existing infrastructure.</p>

          <div class="project">
            <p class="project-name"><a href="https://github.com/Sun-Wukhan/terraformer">Sun-Wukhan/terraformer</a></p>
            <p class="project-desc">Revival fork of GoogleCloudPlatform/terraformer. Coverage work is ongoing: $aws_line are now supported, including the AI-era services (Bedrock, SageMaker, Vertex AI).</p>

            <ul class="releases">
$releases
            </ul>
          </div>
        </section>

        <section aria-labelledby="merged-heading">
          <h2 id="merged-heading">Merged upstream</h2>
          <p class="section-lede">Pull requests merged into third-party projects.</p>

          <ul class="merged-list">
$merged_items
          </ul>
        </section>

        <section aria-labelledby="open-heading">
          <h2 id="open-heading">Open pull requests under review</h2>
          <p class="section-lede">Open pull requests, verified open on $today.</p>

          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Repository</th>
                  <th scope="col">Pull request</th>
                  <th scope="col">Status / engagement</th>
                </tr>
              </thead>
              <tbody>
$open_rows
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <footer>
        <p>All facts verified from github.com on $today. Source: <a href="https://github.com/Sun-Wukhan">github.com/Sun-Wukhan</a>. This page is regenerated automatically from live GitHub data.</p>
      </footer>
    </div>
  </body>
</html>
""")


def main():
    notes = json.loads((ROOT / "data" / "notes.json").read_text())
    site = json.loads((ROOT / "data" / "site.json").read_text())
    current = (ROOT / "index.html").read_text()
    css = re.search(r"<style>\n(.*?)\n    </style>", current, re.S).group(1)

    merged, open_prs = build_sections(fetch_authored_prs(), notes)
    releases = [
        r for r in api_get(f"/repos/{USER}/terraformer/releases?per_page=5") if not r["draft"]
    ][:2]

    aws = f"{site['aws_covered']} of {site['aws_total']} AWS resource types"
    gcp = f"{site['gcp_covered']} GCP resource types"
    if site.get("gcp_total"):
        gcp = f"{site['gcp_covered']} of {site['gcp_total']} GCP resource types"

    today = datetime.now(timezone.utc)
    page = PAGE.substitute(
        css=css,
        aws_line=f"{aws} and {gcp}",
        releases="\n".join(release_item(r, i == 0) for i, r in enumerate(releases)),
        merged_items="\n".join(merged_item(e) for e in merged),
        open_rows="\n".join(open_row(e) for e in open_prs),
        today=f"{today.strftime('%B')} {today.day}, {today.year}",
    )
    (ROOT / "index.html").write_text(page)
    print(f"merged={len(merged)} open={len(open_prs)} releases={len(releases)}")


if __name__ == "__main__":
    sys.exit(main())
