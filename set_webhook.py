"""One-off helper: point your bot's Telegram webhook at your Vercel deployment
(or remove it, to switch back to local polling).

Usage:
    python set_webhook.py https://your-project.vercel.app
    python set_webhook.py --delete

Requires TELEGRAM_BOT_TOKEN (and, for setting a webhook, TELEGRAM_WEBHOOK_SECRET
if you've set one) in your .env.
"""
import asyncio
import sys

from aiogram import Bot

import config


async def main():
    if not config.TOKEN:
        print("TELEGRAM_BOT_TOKEN is not set in .env")
        sys.exit(1)

    bot = Bot(token=config.TOKEN)
    try:
        if len(sys.argv) >= 2 and sys.argv[1] == "--delete":
            await bot.delete_webhook(drop_pending_updates=False)
            print("Webhook removed. The bot can now be run locally via `python main.py`.")
            return

        if len(sys.argv) < 2:
            print(__doc__)
            sys.exit(1)

        base_url = sys.argv[1].rstrip("/")
        webhook_url = f"{base_url}/webhook"
        await bot.set_webhook(
            url=webhook_url,
            secret_token=config.TELEGRAM_WEBHOOK_SECRET or None,
            drop_pending_updates=False,
        )
        info = await bot.get_webhook_info()
        print(f"Webhook set to: {info.url}")
        if not config.TELEGRAM_WEBHOOK_SECRET:
            print(
                "Warning: TELEGRAM_WEBHOOK_SECRET is not set — anyone who finds your "
                "webhook URL could POST fake Telegram updates to it. Set one in .env "
                "and re-run this script."
            )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
