"""Scheduled monitoring — track site scores over time with snapshots."""

import json
import os
import datetime
from pathlib import Path

MONITOR_DIR = Path.home() / ".siteoracle" / "monitors"


def ensure_monitor_dir():
    """Create monitor directory if it doesn't exist."""
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)


def setup_monitor(url, schedule="weekly", max_pages=5, name=None):
    """Set up a monitoring configuration for a URL.

    Args:
        url: The URL to monitor
        schedule: 'daily', 'weekly', or 'monthly'
        max_pages: Pages to crawl each time
        name: Optional friendly name

    Returns:
        dict with monitor config
    """
    ensure_monitor_dir()
    monitor_id = _monitor_id(url)

    config = {
        "id": monitor_id,
        "url": url,
        "name": name or url,
        "schedule": schedule,
        "max_pages": max_pages,
        "created": datetime.datetime.now().isoformat(),
        "last_run": None,
        "history": [],
    }

    config_path = MONITOR_DIR / f"{monitor_id}.json"
    config_path.write_text(json.dumps(config, indent=2))
    return config


def load_monitors():
    """Load all monitoring configs."""
    ensure_monitor_dir()
    monitors = []
    for f in sorted(MONITOR_DIR.glob("*.json")):
        try:
            monitors.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return monitors


def load_monitor(monitor_id):
    """Load a specific monitor by ID."""
    config_path = MONITOR_DIR / f"{monitor_id}.json"
    if not config_path.exists():
        return None
    return json.loads(config_path.read_text())


def save_snapshot(monitor_id, results):
    """Record a new snapshot for a monitor.

    Args:
        monitor_id: The monitor ID
        results: dict with seo, aeo, geo, gbp results
    """
    config = load_monitor(monitor_id)
    if not config:
        return None

    snapshot = {
        "timestamp": datetime.datetime.now().isoformat(),
        "seo_score": results.get("seo", {}).get("score", 0),
        "aeo_score": results.get("aeo", {}).get("score", 0),
        "geo_score": results.get("geo", {}).get("score", 0),
        "gbp_score": results.get("gbp", {}).get("score", 0),
        "combined_score": results.get("combined", 0),
        "issues_count": len(results.get("seo", {}).get("issues", [])),
        "pages_analyzed": results.get("pages_analyzed", 0),
    }

    config["history"].append(snapshot)
    config["last_run"] = snapshot["timestamp"]

    config_path = MONITOR_DIR / f"{monitor_id}.json"
    config_path.write_text(json.dumps(config, indent=2))
    return config


def get_trend(monitor_id, limit=10):
    """Get the trend data for a monitor.

    Returns list of snapshots sorted by time, most recent last.
    """
    config = load_monitor(monitor_id)
    if not config:
        return []

    return config.get("history", [])[-limit:]


def generate_trend_report(monitor_id):
    """Generate a text trend report."""
    config = load_monitor(monitor_id)
    if not config:
        return f"Monitor '{monitor_id}' not found."

    history = config.get("history", [])
    if not history:
        return f"No data for {config.get('name', monitor_id)} yet."

    lines = []
    lines.append("═" * 60)
    lines.append(f"     SITEORACLE MONITOR — {config.get('name', monitor_id)}")
    lines.append(f"     Schedule: {config.get('schedule', 'unknown')}")
    lines.append(f"     Snapshots: {len(history)}")
    lines.append("═" * 60)
    lines.append("")

    headers = f"{'Date':<20} {'SEO':>5} {'AEO':>5} {'GEO':>5} {'GBP':>5} {'Comb':>5}"
    lines.append(headers)
    lines.append("-" * len(headers))

    first_score = history[0]["combined_score"] if history else 0
    last_score = history[-1]["combined_score"] if history else 0

    for snap in history[-10:]:  # Last 10
        ts = snap["timestamp"][:10]
        arrow = "↑" if snap["combined_score"] > (history[history.index(snap) - 1]["combined_score"] if history.index(snap) > 0 else 0) else "↓" if history.index(snap) > 0 else " "
        lines.append(
            f"{ts:<20} {snap['seo_score']:>5} {snap['aeo_score']:>5} "
            f"{snap['geo_score']:>5} {snap['gbp_score']:>5} "
            f"{snap['combined_score']:>5} {arrow}"
        )

    lines.append("")
    change = last_score - first_score
    if len(history) > 1:
        direction = "improved" if change > 0 else "declined"
        lines.append(f"Overall trend: {direction} by {abs(change)} points since tracking began.")

    return "\n".join(lines)


def _monitor_id(url):
    """Generate a unique monitor ID from URL."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.replace("www.", "")
    clean = "".join(c if c.isalnum() else "_" for c in domain)
    return clean or "site"


def delete_monitor(monitor_id):
    """Delete a monitor config."""
    config_path = MONITOR_DIR / f"{monitor_id}.json"
    if config_path.exists():
        config_path.unlink()
        return True
    return False
