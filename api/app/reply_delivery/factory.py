from __future__ import annotations

from app.core.config import get_settings
from app.reply_delivery.base import ReplyDeliveryProvider
from app.reply_delivery.manual_provider import ManualHandoffReplyDeliveryProvider
from app.reply_delivery.webhook_provider import WebhookReplyDeliveryProvider


def get_reply_delivery_provider() -> ReplyDeliveryProvider:
    settings = get_settings()
    if settings.reply_delivery_mode == "webhook" and settings.reply_delivery_webhook_url:
        return WebhookReplyDeliveryProvider(
            webhook_url=settings.reply_delivery_webhook_url,
            token=settings.reply_delivery_webhook_token,
            timeout_seconds=settings.reply_delivery_timeout_seconds,
        )
    return ManualHandoffReplyDeliveryProvider(channel_label=settings.reply_delivery_manual_channel_label)
