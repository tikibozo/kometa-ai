import html as html_lib
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

# Palette for the HTML email (inline styles only — Outlook's Word-based
# renderer ignores <style> blocks and most modern CSS, but honors inline
# colors and table borders).
_GREEN = "#1a7f37"
_RED = "#c9252d"
_MUTE = "#6b7280"
_ZERO = "#9ca3af"
_BORDER = "#e5e7eb"


class NotificationFormatter:
    """Formats status emails as clean plain text plus an Outlook-safe HTML
    alternative (multipart/alternative — HTML renders in Outlook, plain text
    is the fallback for text-only clients)."""

    @staticmethod
    def _format_changes_by_collection(
        changes: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Group changes by collection and action (added/removed)."""
        by_collection: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(
            lambda: {"added": [], "removed": []})

        for change in changes:
            collection = change.get("collection", "unknown")
            action = change.get("action", "unknown")
            if action == "added":
                by_collection[collection]["added"].append(change)
            elif action == "removed":
                by_collection[collection]["removed"].append(change)

        return dict(by_collection)

    @staticmethod
    def _summary_rows(changes: List[Dict[str, Any]]) -> List[Tuple[str, int, int]]:
        """One (collection, added_count, removed_count) row per changed
        collection, sorted by name — the at-a-glance summary table."""
        by_collection = NotificationFormatter._format_changes_by_collection(changes)
        return [
            (name, len(groups["added"]), len(groups["removed"]))
            for name, groups in sorted(by_collection.items())
        ]

    @staticmethod
    def _totals(collection_stats: Optional[Dict[str, Dict[str, Any]]]) -> Tuple[int, float]:
        """(movies processed, API cost) summed across collections this run."""
        stats = collection_stats or {}
        processed = sum(s.get("processed_movies", 0) for s in stats.values())
        cost = sum(s.get("total_cost", 0.0) for s in stats.values())
        return processed, cost

    @staticmethod
    def _counts(
        changes: List[Dict[str, Any]],
        changes_metadata: Optional[Dict[str, Any]],
    ) -> Tuple[int, int, int, bool]:
        """(total, added, removed, truncated) for the overview line."""
        meta = changes_metadata or {}
        truncated = bool(meta.get("truncated", False))
        total = meta.get("total_count", len(changes))
        added = sum(1 for c in changes if c.get("action") == "added")
        removed = sum(1 for c in changes if c.get("action") == "removed")
        return total, added, removed, truncated

    @staticmethod
    def _status_rows(
        collection_status: Optional[Dict[str, Dict[str, int]]]
    ) -> List[Tuple[str, int, int, int, bool]]:
        """(name, members, evaluated, pending, is_current) per collection,
        most-backlog first then alphabetical — the completeness view."""
        cs = collection_status or {}
        rows = [
            (name, s.get("members", 0), s.get("evaluated", 0),
             s.get("pending", 0), s.get("pending", 0) == 0)
            for name, s in cs.items()
        ]
        rows.sort(key=lambda r: (-r[3], r[0]))
        return rows

    @staticmethod
    def _run_status_lines(run_status: Optional[Dict[str, Any]]) -> List[str]:
        """Human-readable budget/quota lines for this run (possibly empty)."""
        rs = run_status or {}
        lines: List[str] = []
        evals_used = rs.get("evals_used")
        max_evals = rs.get("max_evals_per_run")
        deferred = rs.get("deferred", 0)
        if max_evals:
            lines.append(f"Eval budget: {evals_used} of {max_evals} used this run")
        elif evals_used:
            lines.append(f"Evaluations this run: {evals_used}")
        if deferred:
            lines.append(
                f"{deferred} candidate(s) deferred by the budget — resume next run")
        if rs.get("usage_limited"):
            lines.append(
                "Claude usage/quota limit reached — run stopped early; "
                "unprocessed work resumes next run")
        return lines

    # ---- plain text ----------------------------------------------------

    @staticmethod
    def format_summary(
        changes: List[Dict[str, Any]],
        errors: List[Dict[str, Any]],
        next_run_time: Optional[datetime] = None,
        collection_stats: Optional[Dict[str, Dict[str, Any]]] = None,
        version: str = "unknown",
        changes_metadata: Optional[Dict[str, Any]] = None,
        collection_status: Optional[Dict[str, Dict[str, int]]] = None,
        run_status: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Plain-text summary (no Markdown syntax, so it reads cleanly in a
        text-only client)."""
        total, added, removed, truncated = NotificationFormatter._counts(
            changes, changes_metadata)
        rows = NotificationFormatter._summary_rows(changes)
        processed, cost = NotificationFormatter._totals(collection_stats)

        lines: List[str] = [f"Kometa-AI Report (v{version})", "=" * 44, ""]

        overview = f"{total} changes (+{added}/-{removed})"
        if truncated:
            overview += f" [showing most recent {len(changes)}]"
        overview += f"  |  {len(errors)} errors"
        if next_run_time:
            overview += f"  |  next run {next_run_time.strftime('%Y-%m-%d %H:%M')}"
        lines.append(overview)
        lines.append("")

        # At-a-glance table
        if rows:
            name_w = max(10, max(len(name) for name, _, _ in rows))
            lines.append(f"{'Collection'.ljust(name_w)}   Added  Removed")
            for name, a, r in rows:
                a_txt = f"+{a}" if a else "0"
                r_txt = f"-{r}" if r else "0"
                lines.append(f"{name.ljust(name_w)}   {a_txt.rjust(5)}  {r_txt.rjust(7)}")
            lines.append("")

        # Collection status — completeness / backfill backlog
        status_rows = NotificationFormatter._status_rows(collection_status)
        if status_rows:
            lines.append("-- Collection Status --")
            lines.append("")
            name_w = max(10, max(len(n) for n, *_ in status_rows))
            lines.append(f"{'Collection'.ljust(name_w)}   Members  Pending  Status")
            for name, members, _evaluated, pending, current in status_rows:
                state = "current" if current else "backfilling"
                lines.append(
                    f"{name.ljust(name_w)}   {str(members).rjust(7)}  "
                    f"{str(pending).rjust(7)}  {state}")
            lines.append("")
        run_lines = NotificationFormatter._run_status_lines(run_status)
        if run_lines:
            for rl in run_lines:
                lines.append(f"  {rl}")
            lines.append("")

        # Per-collection detail
        if changes:
            lines.append("-- Changes --")
            lines.append("")
            by_collection = NotificationFormatter._format_changes_by_collection(changes)
            for name in sorted(by_collection):
                lines.append(name)
                for m in by_collection[name]["added"]:
                    lines.append(f"  + {m.get('title')} ({m.get('movie_id')})")
                for m in by_collection[name]["removed"]:
                    lines.append(f"  - {m.get('title')} ({m.get('movie_id')})")
                lines.append("")

        # Errors
        if errors:
            lines.append("-- Errors --")
            lines.append("")
            for err in errors:
                ts = (err.get("timestamp", "") or "").split("T")[0]
                lines.append(
                    f"  {ts}: {err.get('message', 'Unknown error')} "
                    f"[{err.get('context', 'unknown')}]")
            lines.append("")

        # Compact footer (replaces the old verbose per-collection stats dump)
        cost_txt = f"${cost:.4f}" if cost else "subscription ($0)"
        lines.append("-" * 44)
        lines.append(f"Processed {processed} movies  |  {cost_txt}")

        return "\n".join(lines)

    # ---- HTML ----------------------------------------------------------

    @staticmethod
    def format_summary_html(
        changes: List[Dict[str, Any]],
        errors: List[Dict[str, Any]],
        next_run_time: Optional[datetime] = None,
        collection_stats: Optional[Dict[str, Dict[str, Any]]] = None,
        version: str = "unknown",
        changes_metadata: Optional[Dict[str, Any]] = None,
        collection_status: Optional[Dict[str, Dict[str, int]]] = None,
        run_status: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Outlook-safe HTML summary — table layout, inline styles only, no
        external resources."""
        total, added, removed, truncated = NotificationFormatter._counts(
            changes, changes_metadata)
        rows = NotificationFormatter._summary_rows(changes)
        processed, cost = NotificationFormatter._totals(collection_stats)
        esc = html_lib.escape

        p: List[str] = [
            '<div style="font-family:Arial,Helvetica,sans-serif;color:#111;max-width:640px;">',
            '<h2 style="margin:0 0 4px;font-size:18px;">Kometa-AI Report</h2>',
        ]

        overview = (
            f'<span style="color:{_GREEN};">+{added}</span> / '
            f'<span style="color:{_RED};">-{removed}</span> '
            f'<span style="color:{_MUTE};">({total} changes)</span>'
        )
        if truncated:
            overview += f' <span style="color:{_MUTE};">— most recent {len(changes)}</span>'
        overview += f' &nbsp;&middot;&nbsp; {len(errors)} errors'
        if next_run_time:
            overview += f' &nbsp;&middot;&nbsp; next run {next_run_time.strftime("%Y-%m-%d %H:%M")}'
        p.append(f'<p style="margin:0 0 16px;color:{_MUTE};font-size:13px;">{overview}</p>')

        if rows:
            p.append('<table cellpadding="6" cellspacing="0" '
                     'style="border-collapse:collapse;font-size:14px;margin-bottom:16px;">')
            p.append(
                f'<tr><th align="left" style="border-bottom:2px solid {_BORDER};">Collection</th>'
                f'<th align="right" style="border-bottom:2px solid {_BORDER};">Added</th>'
                f'<th align="right" style="border-bottom:2px solid {_BORDER};">Removed</th></tr>')
            for name, a, r in rows:
                a_html = (f'<span style="color:{_GREEN};">+{a}</span>' if a
                          else f'<span style="color:{_ZERO};">0</span>')
                r_html = (f'<span style="color:{_RED};">-{r}</span>' if r
                          else f'<span style="color:{_ZERO};">0</span>')
                p.append(
                    f'<tr><td style="border-bottom:1px solid {_BORDER};">{esc(name)}</td>'
                    f'<td align="right" style="border-bottom:1px solid {_BORDER};">{a_html}</td>'
                    f'<td align="right" style="border-bottom:1px solid {_BORDER};">{r_html}</td></tr>')
            p.append('</table>')

        # Collection status — completeness / backfill backlog
        status_rows = NotificationFormatter._status_rows(collection_status)
        if status_rows:
            p.append('<h3 style="margin:16px 0 4px;font-size:15px;">Collection Status</h3>')
            p.append('<table cellpadding="6" cellspacing="0" '
                     'style="border-collapse:collapse;font-size:14px;margin-bottom:12px;">')
            p.append(
                f'<tr><th align="left" style="border-bottom:2px solid {_BORDER};">Collection</th>'
                f'<th align="right" style="border-bottom:2px solid {_BORDER};">Members</th>'
                f'<th align="right" style="border-bottom:2px solid {_BORDER};">Pending</th>'
                f'<th align="left" style="border-bottom:2px solid {_BORDER};">Status</th></tr>')
            for name, members, _evaluated, pending, current in status_rows:
                if current:
                    st = f'<span style="color:{_GREEN};">current</span>'
                    pend_html = f'<span style="color:{_ZERO};">0</span>'
                else:
                    st = f'<span style="color:{_MUTE};">backfilling</span>'
                    pend_html = f'<span style="color:{_MUTE};">{pending}</span>'
                p.append(
                    f'<tr><td style="border-bottom:1px solid {_BORDER};">{esc(name)}</td>'
                    f'<td align="right" style="border-bottom:1px solid {_BORDER};">{members}</td>'
                    f'<td align="right" style="border-bottom:1px solid {_BORDER};">{pend_html}</td>'
                    f'<td style="border-bottom:1px solid {_BORDER};">{st}</td></tr>')
            p.append('</table>')
        run_lines = NotificationFormatter._run_status_lines(run_status)
        if run_lines:
            p.append(f'<p style="margin:0 0 16px;color:{_MUTE};font-size:13px;">'
                     + '<br>'.join(esc(rl) for rl in run_lines) + '</p>')

        if changes:
            by_collection = NotificationFormatter._format_changes_by_collection(changes)
            for name in sorted(by_collection):
                p.append(f'<h3 style="margin:12px 0 4px;font-size:15px;">{esc(name)}</h3>')
                p.append('<ul style="margin:0 0 8px;padding-left:20px;font-size:13px;">')
                for m in by_collection[name]["added"]:
                    p.append(
                        f'<li style="color:{_GREEN};">+ {esc(str(m.get("title")))} '
                        f'<span style="color:{_MUTE};">({m.get("movie_id")})</span></li>')
                for m in by_collection[name]["removed"]:
                    p.append(
                        f'<li style="color:{_RED};">&minus; {esc(str(m.get("title")))} '
                        f'<span style="color:{_MUTE};">({m.get("movie_id")})</span></li>')
                p.append('</ul>')

        if errors:
            p.append(f'<h3 style="margin:12px 0 4px;font-size:15px;color:{_RED};">Errors</h3>')
            p.append('<ul style="margin:0 0 8px;padding-left:20px;font-size:13px;">')
            for err in errors:
                ts = (err.get("timestamp", "") or "").split("T")[0]
                p.append(
                    f'<li>{esc(ts)}: {esc(str(err.get("message", "Unknown error")))} '
                    f'<span style="color:{_MUTE};">[{esc(str(err.get("context", "unknown")))}]</span></li>')
            p.append('</ul>')

        cost_txt = f"${cost:.4f}" if cost else "subscription ($0)"
        p.append(
            f'<p style="margin-top:16px;padding-top:8px;border-top:1px solid {_BORDER};'
            f'color:{_MUTE};font-size:12px;">Processed {processed} movies &middot; '
            f'{cost_txt} &middot; v{esc(version)}</p>')
        p.append('</div>')

        return "\n".join(p)

    @staticmethod
    def format_error_notification(
        error_context: str,
        error_message: str,
        traceback: Optional[str] = None,
        version: str = "unknown",
    ) -> str:
        """Plain-text critical-error notification (used for a pipeline crash,
        separate from the per-run summary)."""
        lines = [
            f"Kometa-AI Error Report (v{version})",
            "=" * 44,
            "",
            f"Error in {error_context}",
            "",
            f"Message: {error_message}",
            "",
        ]

        if traceback:
            lines.append("Traceback:")
            lines.append(traceback)
            lines.append("")

        lines.append(f"Timestamp: {datetime.now().isoformat()}")
        return "\n".join(lines)
