"""
Notification System for Algorithmic Trading Engine

This package provides a comprehensive notification system with:
- Priority-based routing (CRITICAL/WARNING/INFO)
- Email notifications via SendGrid
- HTML email templates
- Rate limiting and batching
- Mock mode for testing

Usage:
    from notifications import (
        NotificationSystem,
        SendGridNotificationService,
        PriorityHandler,
        NotificationPriority
    )

    # Create SendGrid service
    sendgrid = SendGridNotificationService(mock_mode=True)

    # Create notification system
    notif_system = NotificationSystem(
        event_bus=event_bus,
        sendgrid_service=sendgrid
    )

    # Start the system
    await notif_system.start()
"""

# Direct imports to avoid recursion
from .priority import PriorityHandler, NotificationPriority, PriorityConfig
from .sendgrid_client import SendGridNotificationService, MockSendGridClient

# These are imported lazily to avoid circular dependencies
_NotificationSystem = None
_templates = None

def __getattr__(name):
    global _NotificationSystem, _templates

    if name == "NotificationSystem":
        if _NotificationSystem is None:
            from .service import NotificationSystem
            _NotificationSystem = NotificationSystem
        return _NotificationSystem
    elif name == "templates":
        if _templates is None:
            from . import templates as t
            _templates = t
        return _templates
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    'NotificationSystem',
    'SendGridNotificationService',
    'MockSendGridClient',
    'PriorityHandler',
    'NotificationPriority',
    'PriorityConfig',
    'templates',
]

__version__ = '0.1.0'
