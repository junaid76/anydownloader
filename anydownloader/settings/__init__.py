"""
Settings package for anydownloader project.

Usage:
- Development: DJANGO_SETTINGS_MODULE=anydownloader.settings.development
- Production (Render): DJANGO_SETTINGS_MODULE=anydownloader.settings.render
"""

# Default to development settings for backwards compatibility
from .development import *
