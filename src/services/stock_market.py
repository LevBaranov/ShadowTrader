import requests
from datetime import date

from src.config import stock_market_settings
from src.logging_setup import integration_call

from src.models.bond import MoexBond, parse_moex_date
from src.models.error import Error


# Имя интеграции в логах: пишется в logs/moex.log.
SERVICE = "moex"


class Moex:
    """
    Класс для работы с Московской биржей
    """

    def __init__(
        self,
        limit: int = stock_market_settings.MOEX_INDEX_LIMIT,
        base_url: str = stock_market_settings.MOEX_BASE_URL,
    ):

        self.limit = limit
        self.base_url = base_url
        self.session = requests.Session()

    def _fetch_json(self, url: str, params: dict, operation: str = "request") -> dict:
        """Единственная точка выхода на Мосбиржу — здесь же и логируем вызов."""
        with integration_call(SERVICE, operation, url=url) as call:
            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
            except requests.RequestException as e:
                # При ConnectionError/таймауте response нет — не маскируем исходную ошибку.
                status_code = getattr(e.response, "status_code", None)
                raise Error(source="Moex",
                            source_data=e,
                            data={"url": url, "params": params},
                            description=f"Code: {status_code}")

            data = response.json()
            call.add(status=response.status_code)
            call.detail(params=params, response=data)

            return data

    def load_index_rows(self, index_name: str) -> list:
        """Сырые строки analytics состава индекса с Мосбиржи.

        Строка — [indexid, tradedate, ticker, shortnames, weight].
        Пустой список означает «состава нет» — вызывающий решает сам
        (IndexSyncService трактует как ошибку, старые строки не трогает).
        """
        url = f"{self.base_url}/statistics/engines/stock/markets/index/analytics/{index_name}.json"
        rows: list = []
        first_row = None
        start = 0
        while True:
            params = {
                "limit": self.limit,
                "start": start,
                "analytics.columns": "indexid,tradedate,ticker,shortnames,weight",
            }
            data = self._fetch_json(url, params, operation="index_analytics")
            page = data.get("analytics", {}).get("data", [])
            if not page:
                break
            # Защита от сервера, игнорирующего start: иначе цикл бесконечный.
            if first_row is None:
                first_row = page[0]
            elif page[0] == first_row:
                break
            rows.extend(page)
            if len(page) < self.limit:
                break
            start += len(page)
        return rows

    def get_indices(self) -> list[tuple[str, str]]:
        """
        Возвращает список индексов для отслеживания.
        :return: Список (Индекс, Короткое человеко читаемое название индекса).
        """

        url = f"{self.base_url}/securitygroups/stock_index/collections/stock_index_shares/securities.json"
        params = {
            "limit": self.limit,
            "start": 0,
            "securities.columns": "SECID, SHORTNAME, IS_TRADED"
        }
        data = self._fetch_json(url, params, operation="get_indices")
        result = []
        for indexid, shortname, is_traded in data.get("securities", {}).get("data", []):

            if is_traded > 0:
                result.append((indexid, shortname,))

        return result

    # Режимы торгов, которые считаем основными: одна бумага торгуется на
    # нескольких досках, а в справочнике нужен один ряд на secid.
    _PREFERRED_BOND_BOARDS = ("TQCB", "TQOB", "TQIR", "TQTF", "TQBD")

    @classmethod
    def _board_rank(cls, board_name: str) -> int:
        try:
            return cls._PREFERRED_BOND_BOARDS.index(board_name)
        except ValueError:
            return len(cls._PREFERRED_BOND_BOARDS)

    def get_bonds(self) -> list[MoexBond]:
        """
        Возвращает список облигаций с Мосбиржи
        :return: Список облигаций
        """

        url = f"{self.base_url}/engines/stock/markets/bonds/securities.json"
        columns = (
            "SECID,SHORTNAME,BOARDNAME,LOTVALUE,OFFERDATE,"
            "CALLOPTIONDATE,PUTOPTIONDATE,BUYBACKPRICE,ISIN"
        )
        by_secid: dict[str, MoexBond] = {}
        first_row = None
        start = 0
        while True:
            data = self._fetch_json(
                url,
                {
                    "limit": self.limit,
                    "start": start,
                    "securities.columns": columns,
                },
                operation="get_bonds",
            )
            page = data.get("securities", {}).get("data", [])
            if not page:
                break
            # Защита от сервера, игнорирующего start: иначе цикл бесконечный.
            if first_row is None:
                first_row = page[0]
            elif page[0] == first_row:
                break
            for sec in page:
                bond = MoexBond(*sec)
                current = by_secid.get(bond.ticker)
                if (
                    current is None
                    or self._board_rank(bond.board_name)
                    < self._board_rank(current.board_name)
                ):
                    by_secid[bond.ticker] = bond
            if len(page) < self.limit:
                break
            start += len(page)

        return list(by_secid.values())

    def get_bond_offers(self, from_date: date) -> list[tuple[str, str | None, date]]:
        """Оферты по облигациям из bondization: (secid, isin, дата начала подачи заявок).

        Блок offers отдаёт окна оферт: offerdate — дата самой оферты,
        offerdatestart — когда можно начать подавать заявку. Отдаём только
        оферты, ещё не прошедшие (from_date). Пагинация по offers.start.
        """
        url = f"{self.base_url}/statistics/engines/stock/markets/bonds/bondization.json"
        offers: list[tuple[str, str | None, date]] = []
        start = 0
        while True:
            params = {
                "from": from_date.isoformat(),
                "offers.limit": 100,
                "offers.start": start,
            }
            data = self._fetch_json(url, params, operation="get_bond_offers")
            block = data.get("offers") or {}
            columns = block.get("columns", [])
            rows = block.get("data", [])
            if not rows:
                break

            try:
                i_secid = columns.index("secid")
                i_isin = columns.index("isin")
                i_start = columns.index("offerdatestart")
            except ValueError as e:
                raise Error(source="Moex",
                            source_data=e,
                            data={"url": url, "columns": columns},
                            description="offers block missing expected columns")

            for row in rows:
                start_date = parse_moex_date(row[i_start])
                secid = row[i_secid]
                if start_date is None or not secid:
                    # Окно подачи не открыто/не задано — уведомлять не о чем.
                    continue
                offers.append((secid, row[i_isin] or None, start_date))

            if len(rows) < 100:
                break
            start += len(rows)

        return offers