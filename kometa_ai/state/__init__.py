"""
State management for Kometa-AI.

This package provides functionality for persisting decisions and state.
"""

from kometa_ai.state.manager import StateManager
from kometa_ai.state.models import DecisionRecord

__all__ = ['StateManager', 'DecisionRecord']
