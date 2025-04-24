import requests

from models.index import Index, IndexItem
from models.error import Error

from config import settings

class Moex:
    """
    Класс для работы с Московской биржей
    """

    def __init__(self, limit:int = settings.stock_market.limit, base_url:str = settings.stock_market.base_url):

        self.limit = limit
        self.base_url = base_url
        self.session = requests.Session()

    def _fetch_json(self, url: str, params: dict) -> dict:
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Error(source="Moex",
                        source_data=e,
                        data={"url": url, "params": params},
                        description=f"Code: {e.response.status_code}")

    def _load_index_data(self, index_name: str) -> list:
        url = f"{self.base_url}/statistics/engines/stock/markets/index/analytics/{index_name}.json"
        params = {
            "limit": self.limit,
            "start": 0,
            "analytics.columns": "indexid,tradedate,ticker,shortnames,weight",
        }
        data = self._fetch_json(url, params)
        return data.get("analytics", {}).get("data", [])

    def _load_market_data(self, index_name: str) -> tuple[list, list]:
        url = f"{self.base_url}/engines/stock/markets/shares/boards/TQBR/securities.json?index={index_name}"
        params = {
            "limit": self.limit,
            "start": 0,
            "marketdata.columns": "SECID,LAST",
            "securities.columns": "SECID,LOTSIZE,ISIN"
        }
        data = self._fetch_json(url, params)
        market = data.get("marketdata", {}).get("data", [])
        sec = data.get("securities", {}).get("data", [])
        return sec, market

    def get_index_list(self, index_name: str) -> Index:
        """
        Получаем информацию о наполнении индекса
        :param index_name: Наименование индекса
        :return: Данные индекса
        """

        def get_key(array_row, array_type):
            """
            Возвращает позицию ключа "тикера" для типа массива
            :param array_row: Строка массива
            :param array_type: Тип массива
            :return:
            """
            if array_type == "analytics":
                return array_row[2]
            return array_row[0]

        index_name = index_name.upper()

        analytics = self._load_index_data(index_name)
        securities, marketdata = self._load_market_data(index_name)
        date = analytics[0][1] if analytics else ""

        index_by_tickers = {}
        for array_type, array in [("analytics", analytics), ("securities", securities), ("marketdata", marketdata)]:
            for row in array:
                key = get_key(row, array_type)
                if key not in index_by_tickers:
                    index_by_tickers[key] = []
                index_by_tickers[key].extend(row[1:] if array_type != "analytics" else row)


        index = Index(name=index_name, date=date)
        for t, val in index_by_tickers.items():
            item = IndexItem(*val[2:])
            index.items.append(item)

        return index


if __name__ == "__main__":
    m = Moex()
    index_moex = m.get_index_list("IMOEX")
    print(index_moex)
    print(index_moex.to_dataframe())