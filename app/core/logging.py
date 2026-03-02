"""Structured logging setup."""

import logging

import structlog


def setup_logging(debug: bool = False) -> None:
    """Configure structlog with Rich-compatible console output."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO,
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
