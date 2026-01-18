#!/usr/bin/env python3
"""Placeholder worker process - idle worker."""
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Worker started - idle mode (placeholder)")

# Keep worker running
try:
    while True:
        time.sleep(60)
        logger.debug("Worker heartbeat - still idle")
except KeyboardInterrupt:
    logger.info("Worker shutting down")
