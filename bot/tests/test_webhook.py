"""Проверка webhook-обработчика бота (BOT_RUN_MODE=webhook)."""
import asyncio

from aiohttp import ClientSession, web

from bot.main import build_webhook_app

PATH = "/webhook"
TOKEN = "sekret"


class FakeDp:
    def __init__(self):
        self.payloads = []

    async def feed_webhook_update(self, bot, payload):
        self.payloads.append(payload)


def _free_port(site):
    return site._server.sockets[0].getsockname()[1]


def _run(coro):
    return asyncio.run(coro)


def test_webhook_rejects_bad_secret_and_forwards_good():
    async def scenario():
        dp = FakeDp()
        app = build_webhook_app(bot=None, dp=dp, path=PATH, secret_token=TOKEN)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        base = f"http://127.0.0.1:{_free_port(site)}"

        try:
            async with ClientSession() as sess:
                bad = await sess.post(
                    base + PATH,
                    json={"update_id": 1},
                    headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
                )
                assert bad.status == 403

                good = await sess.post(
                    base + PATH,
                    json={"update_id": 2},
                    headers={"X-Telegram-Bot-Api-Secret-Token": TOKEN},
                )
                assert good.status == 200

                missing = await sess.post(base + PATH, json={"update_id": 3})
                assert missing.status == 403
        finally:
            await runner.cleanup()

        # Только апдейт с верным токеном доходит до диспетчера.
        assert dp.payloads == [{"update_id": 2}]

    _run(scenario())


def test_webhook_without_secret_forwards_any():
    async def scenario():
        dp = FakeDp()
        app = build_webhook_app(bot=None, dp=dp, path=PATH, secret_token=None)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        base = f"http://127.0.0.1:{_free_port(site)}"

        try:
            async with ClientSession() as sess:
                res = await sess.post(base + PATH, json={"update_id": 7})
                assert res.status == 200
        finally:
            await runner.cleanup()

        assert dp.payloads == [{"update_id": 7}]

    _run(scenario())
