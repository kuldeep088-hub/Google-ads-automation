import logging
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SlackSender:
    def send(self, message: str, blocks: list | None = None) -> bool:
        if not settings.SLACK_WEBHOOK_URL:
            return False
        payload: dict = {"text": message}
        if blocks:
            payload["blocks"] = blocks
        try:
            resp = httpx.post(settings.SLACK_WEBHOOK_URL, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info("Slack notification sent")
                return True
            logger.error("Slack webhook returned %d: %s", resp.status_code, resp.text)
            return False
        except Exception as e:
            logger.error("Slack send failed: %s", e)
            return False
