#!/usr/bin/env python3
"""Generate repository-hosted SVG GitHub stats using GitHub REST API."""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets'
USER = os.environ.get('GITHUB_PROFILE_USER', 'AmmadNaseem')
TOKEN = os.environ.get('GH_STATS_TOKEN') or os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN', '')
API = 'https://api.github.com'


def request(path):
    req = urllib.request.Request(API + path, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'profile-svg-stats-generator',
        'X-GitHub-Api-Version': '2022-11-28',
        **({'Authorization': 'Bearer ' + TOKEN} if TOKEN else {}),
    })
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.load(resp)


def get_pages(path):
    data = []
    for page in range(1, 21):
        sep = '&' if '?' in path else '?'
        chunk = request(f'{path}{sep}per_page=100&page={page}')
        if not isinstance(chunk, list):
            raise RuntimeError('Expected a list from GitHub API')
        data.extend(chunk)
        if len(chunk) < 100:
            break
    return data


def svg(title, subtitle, items, width=620, height=250):
    # Values are escaped before embedding in SVG.
    lines = []
    for idx, (label, value) in enumerate(items):
        y = 111 + idx * 33
        lines.append(f'<text x="32" y="{y}" fill="#a8b7d0" font-size="15">{escape(str(label))}</text>')
        lines.append(f'<text x="{width-32}" y="{y}" text-anchor="end" fill="#eaf8ff" font-weight="700" font-size="17">{escape(str(value))}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
<defs><linearGradient id="accent"><stop stop-color="#5ce1e6"/><stop offset="1" stop-color="#a78bfa"/></linearGradient></defs>
<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="20" fill="#101827" stroke="#263a53" stroke-width="2"/>
<rect x="28" y="25" width="5" height="39" rx="2" fill="url(#accent)"/>
<text x="46" y="44" fill="#eaf8ff" font-size="21" font-family="Arial, sans-serif" font-weight="700">{escape(title)}</text>
<text x="46" y="63" fill="#83a4bf" font-size="12" font-family="Arial, sans-serif">{escape(subtitle)}</text>
<line x1="30" x2="{width-30}" y1="78" y2="78" stroke="#263a53"/>
<g font-family="Arial, sans-serif">{''.join(lines)}</g>
</svg>'''


def main():
    info = request('/users/' + urllib.parse.quote(USER))
    repos = get_pages('/users/' + urllib.parse.quote(USER) + '/repos?type=owner&sort=updated')
    public = [r for r in repos if not r.get('private') and not r.get('fork')]
    stars = sum(int(r.get('stargazers_count') or 0) for r in public)
    forks = sum(int(r.get('forks_count') or 0) for r in public)
    # GitHub language API returns bytes per language per repository.
    languages = Counter()
    for repo in public:
        if repo.get('size', 0) == 0:
            continue
        try:
            langs = request('/repos/' + urllib.parse.quote(USER) + '/' + urllib.parse.quote(repo['name']) + '/languages')
            languages.update({k: int(v) for k, v in langs.items()})
        except (urllib.error.HTTPError, urllib.error.URLError) as exc:
            print(f"Warning: could not fetch languages for {repo['name']}: {exc}", file=sys.stderr)
    OUT.mkdir(exist_ok=True)
    stats = [
        ('Public repositories', info.get('public_repos', 0)),
        ('Original public repositories', len(public)),
        ('Stars on original repositories', stars),
        ('Forks of original repositories', forks),
        ('Followers', info.get('followers', 0)),
    ]
    (OUT / 'github-stats.svg').write_text(svg('GITHUB // SIGNAL', 'Live GitHub REST API data · refreshed by Actions', stats, height=290), encoding='utf-8')
    total = sum(languages.values())
    if total:
        top = languages.most_common(5)
        items = [(lang, f'{bytes_count / total * 100:.1f}%') for lang, bytes_count in top]
        description = 'Language byte share · original public repositories'
    else:
        items = [('No language data available', '—')]
        description = 'Original public repositories'
    (OUT / 'top-languages.svg').write_text(svg('CODE // LANGUAGES', description, items, height=290), encoding='utf-8')
    print(f'Generated SVGs for {USER}: {len(public)} original public repositories, {len(languages)} languages')


if __name__ == '__main__':
    try:
        main()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, RuntimeError) as exc:
        sys.exit(f'GitHub API request failed: {exc}')
