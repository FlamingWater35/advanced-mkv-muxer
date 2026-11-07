"""Checking whether a newer Advanced MKV Muxer release has been published.

Like :mod:`packages.ToolUpdates.MkvToolNixUpdater` this module is free of Qt
imports so the release logic can be tested without a GUI. Network access is
injectable, which is what the unit tests use.

The GitHub API is queried first because it returns the release page URL and the
release notes in one document. Unauthenticated API calls are rate limited, so
the public Atom feed of the repository is used as a fallback; it carries the
same version tag and link without a quota.
"""

import json
import re
from dataclasses import dataclass

from packages.ToolUpdates.MkvToolNixUpdater import (
    UpdateError,
    fetch_url_text,
    is_newer,
    parse_version,
    version_key,
)

GITHUB_REPOSITORY = "FlamingWater35/advanced-mkv-muxer"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
RELEASES_ATOM_URL = f"https://github.com/{GITHUB_REPOSITORY}/releases.atom"
LATEST_RELEASE_PAGE_URL = f"https://github.com/{GITHUB_REPOSITORY}/releases/latest"

ATOM_ENTRY_PATTERN = re.compile(r"<entry>(.*?)</entry>", re.DOTALL)
ATOM_TAG_PATTERN = re.compile(r"/tag/v?(\d+(?:\.\d+)+)")
ATOM_LINK_PATTERN = re.compile(r'<link[^>]*rel="alternate"[^>]*href="([^"]+)"')
ATOM_TITLE_PATTERN = re.compile(r"<title>(.*?)</title>", re.DOTALL)


@dataclass(frozen=True)
class AppRelease:
    """A published application release."""

    version: str
    url: str
    name: str = ""
    notes: str = ""


@dataclass(frozen=True)
class AppUpdateStatus:
    current: str | None
    latest: str | None
    update_available: bool
    release_url: str
    release_name: str = ""


def _clean_text(text: str) -> str:
    return " ".join(str(text or "").split())


def release_from_github_api(payload: str) -> AppRelease | None:
    """Read a release from a GitHub ``releases/latest`` API response."""
    data = json.loads(payload)
    if not isinstance(data, dict):
        return None
    version = parse_version(str(data.get("tag_name", "")))
    if not version:
        return None
    return AppRelease(
        version=version,
        url=str(data.get("html_url") or LATEST_RELEASE_PAGE_URL),
        name=_clean_text(data.get("name", "")),
        notes=str(data.get("body") or ""),
    )


def release_from_releases_atom(feed: str) -> AppRelease | None:
    """Read the newest release from the repository's Atom feed."""
    releases = []
    for entry in ATOM_ENTRY_PATTERN.findall(feed):
        tag_match = ATOM_TAG_PATTERN.search(entry)
        if tag_match is None:
            continue
        link_match = ATOM_LINK_PATTERN.search(entry)
        title_match = ATOM_TITLE_PATTERN.search(entry)
        releases.append(AppRelease(
            version=tag_match.group(1),
            url=link_match.group(1) if link_match else LATEST_RELEASE_PAGE_URL,
            name=_clean_text(title_match.group(1)) if title_match else "",
        ))
    if not releases:
        return None
    return max(releases, key=lambda release: version_key(release.version))


def latest_release(fetch_text=fetch_url_text) -> AppRelease:
    """Return the newest published application release.

    The GitHub API is tried first; the Atom feed covers the case where the API
    is rate limited or blocked.
    """
    problems = []
    for url, parser in (
            (RELEASES_API_URL, release_from_github_api),
            (RELEASES_ATOM_URL, release_from_releases_atom),
    ):
        try:
            found = parser(fetch_text(url))
        except Exception as exception:  # noqa: BLE001 - reported to the user
            problems.append(f"{url}: {exception}")
            continue
        if found is not None:
            return found
        problems.append(f"{url}: no release information found")

    raise UpdateError("Could not determine the latest Advanced MKV Muxer version.\n" + "\n".join(problems))


def check_for_app_update(current_version: str | None, fetch_text=fetch_url_text) -> AppUpdateStatus:
    """Compare ``current_version`` with the newest published release."""
    release = latest_release(fetch_text=fetch_text)
    return AppUpdateStatus(
        current=current_version,
        latest=release.version,
        update_available=is_newer(release.version, current_version),
        release_url=release.url or LATEST_RELEASE_PAGE_URL,
        release_name=release.name,
    )
