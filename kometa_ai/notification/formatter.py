import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from collections import defaultdict
import json

logger = logging.getLogger(__name__)


class NotificationFormatter:
    """Formatter for email notifications with detailed information about changes and errors."""

    @staticmethod
    def _format_changes_by_collection(changes: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Group changes by collection and action (added/removed).

        Args:
            changes: List of tag changes from the state manager

        Returns:
            Dictionary with collections as keys and action groups as values
        """
        by_collection: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: {"added": [], "removed": []})

        for change in changes:
            collection = change.get("collection", "unknown")
            action = change.get("action", "unknown")

            if action == "added":
                by_collection[collection]["added"].append(change)
            elif action == "removed":
                by_collection[collection]["removed"].append(change)

        return dict(by_collection)

    @staticmethod
    def _format_collection_changes(
        collection_name: str,
        added: List[Dict[str, Any]],
        removed: List[Dict[str, Any]]
    ) -> str:
        """Format changes for a single collection.

        Args:
            collection_name: Collection name
            added: List of added movies
            removed: List of removed movies

        Returns:
            Formatted section for this collection
        """
        lines = [f"### {collection_name}", ""]

        if not added and not removed:
            lines.append("No changes")
            return "\n".join(lines)

        if added:
            lines.append(f"**Added**: {len(added)}")
            for movie in added:
                lines.append(f"- {movie.get('title')} ({movie.get('movie_id')})")
            lines.append("")

        if removed:
            lines.append(f"**Removed**: {len(removed)}")
            for movie in removed:
                lines.append(f"- {movie.get('title')} ({movie.get('movie_id')})")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_errors(errors: List[Dict[str, Any]]) -> str:
        """Format error information.

        Args:
            errors: List of errors from the state manager

        Returns:
            Formatted error section
        """
        if not errors:
            return "No errors encountered"

        lines = []

        # Group errors by context
        context_errors = defaultdict(list)
        for error in errors:
            context = error.get("context", "unknown")
            context_errors[context].append(error)

        # Format each context group
        for context, error_list in context_errors.items():
            lines.append(f"### {context}")
            lines.append("")
            for error in error_list:
                timestamp = error.get("timestamp", "").split("T")[0]  # Just date part
                message = error.get("message", "Unknown error")
                lines.append(f"- {timestamp}: {message}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _format_collection_stats(collection_stats: Dict[str, Dict[str, Any]]) -> str:
        """Format processing statistics for collections.

        Args:
            collection_stats: Statistics from the movie processor

        Returns:
            Formatted stats section
        """
        if not collection_stats:
            return "No statistics available"

        lines = []

        total_processed = 0
        total_cost = 0.0
        total_input_tokens = 0
        total_output_tokens = 0
        collections_processed = 0

        for collection, stats in collection_stats.items():
            processed = stats.get("processed_movies", 0)
            from_cache = stats.get("from_cache", 0)
            cost = stats.get("total_cost", 0.0)

            lines.append(f"### {collection}")
            lines.append(f"- Processed: {processed} movies")
            lines.append(f"- From cache: {from_cache} movies")
            lines.append(f"- API cost: ${cost:.4f}")
            lines.append("")

            total_processed += processed
            total_cost += cost
            total_input_tokens += stats.get("total_input_tokens", 0)
            total_output_tokens += stats.get("total_output_tokens", 0)
            collections_processed += 1

        # Add summary stats
        lines.insert(0, "")
        lines.insert(0, f"- Total cost: ${total_cost:.4f}")
        lines.insert(0, f"- Total tokens: {total_input_tokens + total_output_tokens}")
        lines.insert(0, f"- Collections processed: {collections_processed}")
        lines.insert(0, f"- Total processed: {total_processed} movies")
        lines.insert(0, "### Summary")

        return "\n".join(lines)

    @staticmethod
    def format_summary(
        changes: List[Dict[str, Any]],
        errors: List[Dict[str, Any]],
        next_run_time: Optional[datetime] = None,
        collection_stats: Optional[Dict[str, Dict[str, Any]]] = None,
        version: str = "unknown"
    ) -> str:
        """Format a summary email with changes, errors, and processing statistics.

        Args:
            changes: List of tag changes from the state manager
            errors: List of errors from the state manager
            next_run_time: Next scheduled run time
            collection_stats: Processing statistics from the movie processor
            version: Application version

        Returns:
            Formatted email body in Markdown format
        """
        lines = [f"# Kometa-AI Summary (v{version})", ""]

        # Summary section
        has_changes = len(changes) > 0
        has_errors = len(errors) > 0

        lines.append("## Overview")
        lines.append("")
        lines.append(f"- Total changes: {len(changes)}")
        lines.append(f"- Errors: {len(errors)}")

        if next_run_time:
            formatted_time = next_run_time.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"- Next scheduled run: {formatted_time}")

        lines.append("")

        # Changes by collection
        if has_changes:
            lines.append("## Changes by Collection")
            lines.append("")

            by_collection = NotificationFormatter._format_changes_by_collection(changes)

            for collection, actions in by_collection.items():
                collection_section = NotificationFormatter._format_collection_changes(
                    collection, actions["added"], actions["removed"]
                )
                lines.append(collection_section)
        else:
            lines.append("## Changes")
            lines.append("")
            lines.append("No changes were made in this run")
            lines.append("")

        # Errors section
        lines.append("## Errors")
        lines.append("")
        error_section = NotificationFormatter._format_errors(errors)
        lines.append(error_section)
        lines.append("")

        # Processing stats
        if collection_stats:
            lines.append("## Processing Statistics")
            lines.append("")
            stats_section = NotificationFormatter._format_collection_stats(collection_stats)
            lines.append(stats_section)
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_error_notification(
        error_context: str,
        error_message: str,
        traceback: Optional[str] = None,
        version: str = "unknown"
    ) -> str:
        """Format an error notification for critical errors.

        Args:
            error_context: Context where the error occurred
            error_message: Error message
            traceback: Optional traceback
            version: Application version

        Returns:
            Formatted error notification in Markdown format
        """
        lines = [f"# Kometa-AI Error Report (v{version})", ""]

        lines.append(f"## Error in {error_context}")
        lines.append("")
        lines.append(f"**Error message**: {error_message}")
        lines.append("")

        if traceback:
            lines.append("## Traceback")
            lines.append("")
            lines.append("```")
            lines.append(traceback)
            lines.append("```")
            lines.append("")

        lines.append("## System Information")
        lines.append("")
        lines.append(f"- Version: {version}")
        lines.append(f"- Timestamp: {datetime.now().isoformat()}")
        lines.append("")

        return "\n".join(lines)
