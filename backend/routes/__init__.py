"""
Routes package for Oil & Gas Field Operations Demo
Contains all API endpoint blueprints organized by functionality
"""

from .dashboard import dashboard_bp
from .sensors import sensors_bp
from .alerts import alerts_bp
from .search import search_bp
from .sessions import sessions_bp
from .monitoring import monitoring_bp

__all__ = [
    'dashboard_bp',
    'sensors_bp',
    'alerts_bp',
    'search_bp',
    'sessions_bp',
    'monitoring_bp'
]

