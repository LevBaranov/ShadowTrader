import time

import httpx

from bot.logging_setup import integration_call

# Обновляем токен незадолго до истечения, чтобы не ловить 401 на границе.
TOKEN_REFRESH_MARGIN_SEC = 30

# Имя интеграции в логах: пишется в logs/api.log.
SERVICE = "api"


class ApiError(Exception):
    """Ошибка API: статус + machine-readable detail."""

    def __init__(self, status_code: int, detail: str | None = None):
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class TelegramNotLinkedError(Exception):
    """Telegram-аккаунт не привязан ни к одной учётке."""


def _detail(response: httpx.Response) -> str | None:
    try:
        return response.json().get("detail")
    except Exception:
        return None


class ShadowTraderApi:

    def __init__(self, base_url: str, service_key: str, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=60.0)
        self._service_key = service_key
        # telegram_id -> (access_token, monotonic-время истечения)
        self._tokens: dict[int, tuple[str, float]] = {}

    async def close(self) -> None:
        await self._client.aclose()

    async def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Единственная точка выхода в бэкенд — здесь же логируем вызов.

        Заголовки в лог не попадают: там сервисный ключ и JWT.
        """
        with integration_call(SERVICE, f"{method} {path}") as call:
            response = await self._client.request(method, path, **kwargs)

            call.add(status=response.status_code)
            call.detail(request=kwargs.get("json") or kwargs.get("params"), response=response.text)

            if response.status_code >= 400:
                call.failed(_detail(response) or "http_error")

            return response

    # --- сервисные эндпоинты (X-Service-Key) ---

    async def _service_post(self, path: str, telegram_id: int) -> dict:
        response = await self._send(
            "POST", path,
            json={"telegramId": telegram_id},
            headers={"X-Service-Key": self._service_key},
        )
        return self._handle(response)

    async def register_telegram_user(self, telegram_id: int) -> dict:
        return await self._service_post("/service/telegram/register", telegram_id)

    async def create_link_request(self, telegram_id: int) -> dict:
        return await self._service_post("/service/telegram/link-requests", telegram_id)

    async def is_linked(self, telegram_id: int) -> bool:
        try:
            await self._get_token(telegram_id)
            return True
        except TelegramNotLinkedError:
            return False

    # --- обмен токена и доменные запросы ---

    async def _get_token(self, telegram_id: int, force: bool = False) -> str:
        cached = self._tokens.get(telegram_id)
        if not force and cached and cached[1] > time.monotonic() + TOKEN_REFRESH_MARGIN_SEC:
            return cached[0]

        response = await self._send(
            "POST", "/service/telegram/token",
            json={"telegramId": telegram_id},
            headers={"X-Service-Key": self._service_key},
        )

        if response.status_code == 404 and _detail(response) == "telegram_not_linked":
            self._tokens.pop(telegram_id, None)
            raise TelegramNotLinkedError(telegram_id)

        data = self._handle(response)
        token = data["accessToken"]
        self._tokens[telegram_id] = (token, time.monotonic() + data["expiresIn"])
        return token

    async def _request(self, method: str, path: str, telegram_id: int, **kwargs):
        token = await self._get_token(telegram_id)
        response = await self._send(
            method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs
        )

        if response.status_code == 401:
            # Токен мог протухнуть/быть отозван — один повтор со свежим.
            token = await self._get_token(telegram_id, force=True)
            response = await self._send(
                method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs
            )

        return self._handle(response)

    @staticmethod
    def _handle(response: httpx.Response):
        if response.status_code >= 400:
            raise ApiError(response.status_code, _detail(response))
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    # --- доменные методы ---

    async def get_profile(self, telegram_id: int) -> dict:
        return await self._request("GET", "/users/me/profile", telegram_id)

    async def get_strategies(self, telegram_id: int) -> list[dict]:
        return await self._request("GET", "/strategies", telegram_id)

    async def get_rebalance_preview(self, telegram_id: int, strategy_id: str) -> dict:
        return await self._request(
            "GET", f"/strategies/{strategy_id}/rebalance", telegram_id
        )

    async def execute_rebalance(self, telegram_id: int, strategy_id: str) -> dict:
        return await self._request(
            "POST", "/portfolios/balance", telegram_id,
            json={"strategyId": strategy_id},
        )

    async def create_strategy(
            self, telegram_id: int, brokers_account_id: str, index_id: str
    ) -> dict:
        return await self._request(
            "POST", "/strategies", telegram_id,
            json={
                "brokersAccountId": brokers_account_id,
                "stockMarketsIndexId": index_id,
            },
        )

    async def delete_strategy(self, telegram_id: int, strategy_id: str) -> None:
        await self._request("DELETE", f"/strategies/{strategy_id}", telegram_id)

    async def request_email_change(
            self, telegram_id: int, email: str, password: str | None = None
    ) -> dict:
        payload = {"email": email}
        if password:
            payload["password"] = password
        return await self._request("POST", "/users/me/email", telegram_id, json=payload)

    async def confirm_email_change(self, telegram_id: int, code: str) -> dict:
        return await self._request(
            "POST", "/users/me/email/confirm", telegram_id, json={"code": code}
        )

    async def resend_email_code(self, telegram_id: int) -> dict:
        return await self._request("POST", "/users/me/email/resend", telegram_id)

    async def cancel_email_change(self, telegram_id: int) -> None:
        await self._request("DELETE", "/users/me/email/pending", telegram_id)

    async def unlink_telegram(self, telegram_id: int) -> None:
        await self._request("DELETE", "/users/me/telegram-link", telegram_id)

    async def get_brokers(self, telegram_id: int) -> list[dict]:
        return await self._request("GET", "/brokers", telegram_id)

    async def save_broker(
            self, telegram_id: int, broker_name: str, token: str, sandbox: bool = False
    ) -> dict:
        return await self._request(
            "PUT", "/brokers", telegram_id,
            json={"brokerName": broker_name, "token": token, "sandbox": sandbox},
        )

    async def update_broker(self, telegram_id: int, broker_id: str, commission) -> dict:
        """Комиссия брокера долей (0.003 = 0,3 %) — без токена и проверки у брокера."""
        return await self._request(
            "PATCH", f"/brokers/{broker_id}", telegram_id,
            json={"commission": str(commission)},
        )

    async def get_accounts(self, telegram_id: int) -> list[dict]:
        """Все счета пользователя по всем брокерам одним списком."""
        return await self._request("GET", "/accounts", telegram_id)

    async def refresh_accounts(self, telegram_id: int) -> list[dict]:
        return await self._request("POST", "/accounts/refresh", telegram_id)

    async def get_indices(self, telegram_id: int) -> list[dict]:
        return await self._request("GET", "/indices", telegram_id)

    async def get_bond_events(self, telegram_id: int, brokers_account_id: str) -> list[dict]:
        return await self._request(
            "GET", "/bonds/events", telegram_id,
            params={"brokersAccountId": brokers_account_id},
        )

    async def list_tasks(self, telegram_id: int) -> list[dict]:
        return await self._request("GET", "/tasks", telegram_id)

    async def create_task(
            self, telegram_id: int, task_type: str, frequency: str, params: dict
    ) -> dict:
        return await self._request(
            "POST", "/tasks", telegram_id,
            json={"type": task_type, "frequency": frequency, "params": params},
        )

    async def delete_task(self, telegram_id: int, task_id: str) -> None:
        await self._request("DELETE", f"/tasks/{task_id}", telegram_id)
