# Configure logging FIRST before anything else
import logging
from pathlib import Path

# Create logs directory
logs_dir = Path(__file__).parent.parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

# Import logger after directory setup
from app.core.logger import logger, configure_logging, register_logger

# Initialize logging using the logger module's initializer
configure_logging()

__all__ = ["logger", "configure_logging", "register_logger"]
