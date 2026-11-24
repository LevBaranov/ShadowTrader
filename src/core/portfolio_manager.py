import datetime
import logging

from src.core.balancer import Balancer

from src.models.balancer_params import BalancerParams
from src.models.bond import MoexBond, Bond
from src.models.positions import Positions
from src.models.action import Action
from src.models.error import Error
from src.models.index import  Index, IndexItem
from src.models.index_composition import CompositionSnapshot
from src.models.instrument_directory import InstrumentDirectory
from src.models.rebalance import RebalancePreview, PortfolioPosition

from src.services.broker import TBroker, TAccount
from src.services.stock_market import Moex


logger = logging.getLogger(__name__)


class PortfolioManager:
    """
    Класс для управления портфелем. Смотрит текущие позиции, анализирует индекс,
    рассчитывает что нужно сделать для балансировки
    """

    def __init__(self, broker_token: str, account_id: str = None, sandbox: bool = None):
        """
        :param broker_token: Токен доступа к брокеру. Резолвится на сервисном слое из БД,
            ядро не знает, откуда он взялся.
        :param account_id: Идентификатор аккаунта пользователя в формате uuid.
        :param sandbox: Режим песочницы. Если None — используется значение по умолчанию из TBroker.
        """
        self.actions: list[Action] = []

        broker_kwargs = {"token": broker_token}
        if sandbox is not None:
            broker_kwargs["sandbox"] = sandbox
        self.broker = TBroker(**broker_kwargs)
        self.sandbox = sandbox

        self.account_client: TAccount | None = None
        if account_id:
            self.set_account(account_id)

        self._index_cache: dict[tuple[str, datetime.date], Index] = {}
        self.moex = Moex()

    def set_account(self, account_id: str) -> None:
        """
        Установка текущего аккаунта для работы
        :param account_id: Идентификатор аккаунта пользователя в формате uuid
        :return:
        """
        self.account_client = TAccount(account_id, self.broker)
        self.actions = []

    def _ensure_account(self, account_id: str | None) -> None:
        """Ленивая привязка счёта: пересоздаём клиент при смене account_id."""
        if not self.account_client:
            if not account_id:
                raise ValueError("Account client is not initialized and account_id is not provided")
            self.set_account(account_id)
        elif account_id and self.account_client.account_id != account_id:
            self.set_account(account_id)

    def _check_directory(self, directory: InstrumentDirectory | None) -> None:
        """Контур справочника обязан совпадать с контуром счёта.

        Чужая песочница/бой в расчёте — молчаливая подмена вселенной
        инструментов, ловим сразу, а не по странным ценам.
        """
        if (
            directory is not None
            and self.sandbox is not None
            and directory.sandbox != self.sandbox
        ):
            raise ValueError(
                f"Directory contour (sandbox={directory.sandbox}) does not match "
                f"account contour (sandbox={self.sandbox})"
            )

    def get_portfolio(
        self, account_id: str = None, *, directory: InstrumentDirectory | None = None
    ) -> Positions:
        """
        Вернуть текущие позиции по аккаунту
        :param account_id: Идентификатор аккаунта пользователя в формате uuid.
        :param directory: Снимок справочника инструментов.
            None — живой поиск у брокера, только аварийный путь.
        :return: Открытые позиции
        """
        self._check_directory(directory)
        self._ensure_account(account_id)

        return self.account_client.get_positions(directory=directory)

    def get_index(
        self, index_name: str, composition: CompositionSnapshot,
        *, directory: InstrumentDirectory | None = None,
    ) -> Index:
        """
        Собрать данные индекса для расчёта: состав из БД (слепок), мета инструментов —
        из справочника (directory), цены — у брокера. Бумаги, которых нет в справочнике
        или без цены, пропускаются с варнингом. Результат кешируется на торговую дату состава.
        :param index_name: Название индекса
        :param composition: Слепок состава из БД (или on-demand добора)
        :param directory: Снимок справочника инструментов.
            None — живой поиск у брокера, только аварийный путь.
        :return: Состав индекса с ценами брокера
        """
        self._check_directory(directory)
        cache_key = (index_name.upper(), composition.tradedate)
        if cache_key not in self._index_cache:
            self._index_cache[cache_key] = self._build_index(
                composition, directory=directory
            )
        return self._index_cache[cache_key]

    def _build_index(
        self, composition: CompositionSnapshot,
        *, directory: InstrumentDirectory | None = None,
    ) -> Index:
        resolved = self._resolve_shares(composition, directory)
        if not resolved:
            raise ValueError(
                f"Нет данных для расчёта по {composition.index_name}: "
                "ни один тикер состава не нашёлся у брокера"
            )

        prices = self.broker.get_last_prices_by_uid(
            [share.uid for _, share in resolved.values()]
        )
        items = self._load_items(composition, resolved, prices)

        if not items:
            raise ValueError(
                f"Нет данных для расчёта по {composition.index_name}: "
                "ни один тикер состава не нашёлся у брокера с ценой"
            )

        return Index(
            name=composition.index_name,
            date=composition.tradedate.isoformat() if composition.tradedate else "",
            items=items,
        )

    def _resolve_shares(self, composition, directory):
        """Тикеры состава -> (строка состава, Share). Ненайденные — warning и пропуск."""
        resolved = {}
        for row in composition.rows:
            share = self.broker.find_share(row.ticker, "ticker", directory=directory)
            if share is None:
                logger.warning(
                    "Тикер %s из состава %s не найден — пропускаем",
                    row.ticker, composition.index_name,
                )
                continue
            resolved[row.ticker] = (row, share)
        return resolved

    @staticmethod
    def _load_items(composition, resolved, prices) -> list:
        """Пары (строка, Share) + цены -> элементы индекса. Без цены — пропуск."""
        items = []
        for ticker, (row, share) in resolved.items():
            price = prices.get(share.uid)
            if price is None:
                logger.warning(
                    "Нет цены у брокера для %s (%s) — пропускаем",
                    ticker, composition.index_name,
                )
                continue
            items.append(IndexItem(
                ticker=ticker,
                shortname=row.shortname,
                weight=row.weight,
                lot_size=share.lot_size,
                isin=share.isin,
                last_price=price,
            ))
        return items

    def execute_actions(self, actions: list[Action] | None = None) -> tuple[list[Action], list[Error]]:
        """
        Выполнить действия по аккаунту.
        :param actions: Явный список к исполнению (готовый план клиента).
            None — накопленные self.actions (после calculate_rebalance, путь шедуллера).
        :return: Список действий выполненных успешно и список произошедших ошибок
        """
        if not self.account_client:
            raise ValueError("Account client is not initialized")

        success_action_list: list[Action] = []
        error_action_list: list[Error] = []
        to_run = actions if actions is not None else self.actions
        for action in to_run:
            try:
                self.account_client.create_order(action)
                success_action_list.append(action)
            except Error as err:
                error_action_list.append(err)

        return success_action_list, error_action_list

    def get_bonds_with_events(self, account_id: str = None, since: datetime.date | None = None,
                                *, directory: InstrumentDirectory | None = None,
                                moex_bonds: list[MoexBond] | None = None) -> list[Bond]:
        """
        Возвращает облигации на счёте, по которым впереди есть оферта или колл-опцион.

        * Получаем список всех облигаций у Мосбиржи (из кэша или переданный).
        * Получаем облигации на аккаунте брокера.
        * Оставляем только те бумаги со счёта, у которых есть событие в будущем,
          и прикладываем к каждой список этих событий с датами.
        :param account_id: Идентификатор аккаунта пользователя в формате uuid.
        :param since: С какой даты считать событие предстоящим (по умолчанию — сегодня).
        :param directory: Снимок справочника инструментов.
            None — живой поиск у брокера, только аварийный путь.
        :param moex_bonds: Готовый список облигаций Мосбиржи.
            None — запрос к self.moex.get_bonds().
        :return: Список облигаций с предстоящими событиями.
        """
        self._check_directory(directory)
        self._ensure_account(account_id)

        if since is None:
            since = datetime.date.today()

        if moex_bonds is None:
            moex_bonds = self.moex.get_bonds()

        moex_bonds_by_ticker = {moex_bond.ticker: moex_bond for moex_bond in moex_bonds}
        moex_bonds_by_isin = {
            moex_bond.isin: moex_bond for moex_bond in moex_bonds if moex_bond.isin
        }

        portfolio_bonds = self.account_client.get_positions(directory=directory).bonds

        bonds_with_events = []
        for _portfolio_bond in portfolio_bonds:
            moex_bond = moex_bonds_by_ticker.get(_portfolio_bond.ticker)

            if moex_bond is None and directory is not None:
                meta = directory.by_ticker.get(_portfolio_bond.ticker)
                if meta is not None and meta.isin:
                    moex_bond = moex_bonds_by_isin.get(meta.isin)

            if moex_bond is None:
                moex_bond = moex_bonds_by_isin.get(_portfolio_bond.ticker)

            if moex_bond is None:
                logger.warning(
                    "Облигация со счёта %s не найдена в справочнике MOEX",
                    _portfolio_bond.ticker,
                )
                continue

            upcoming = sorted(
                (event for event in moex_bond.events() if event.date >= since),
                key=lambda event: event.date,
            )
            if not upcoming:
                continue

            bonds_with_events.append(
                Bond(
                    uid=_portfolio_bond.uid,
                    figi=_portfolio_bond.figi,
                    ticker=_portfolio_bond.ticker,
                    lot_size=_portfolio_bond.lot_size,
                    type=_portfolio_bond.type,
                    isin=None,
                    offer_date=moex_bond.offer_date,
                    call_option_date=moex_bond.call_option_date,
                    put_option_date=moex_bond.put_option_date,
                    buy_back_price=moex_bond.buy_back_price,
                    short_name=moex_bond.short_name,
                    balance=_portfolio_bond.balance,
                    events=upcoming,
                )
            )

        return bonds_with_events

    def calculate_rebalance(
        self, index_name: str, params: BalancerParams, composition: CompositionSnapshot,
        *, directory: InstrumentDirectory | None = None,
    ) -> RebalancePreview:
        """
        Метод для расчёта действий балансировки, кроме действий возвращает данные по весу внутри портфеля и индекса.
        :param index_name: Наименование индекса для расчёта
        :param params: Параметры расчёта — настройки брокера и стратегии.
        :param composition: Слепок состава индекса (из БД или on-demand добора).
        :param directory: Снимок справочника инструментов.
            None — живой поиск у брокера, только аварийный путь.
        :return: Действия, свободные средства и позиции с весом по каждой.
        """

        portfolio = self.get_portfolio(directory=directory)
        portfolio_items = { share.ticker: share for share in portfolio.shares }

        index = self.get_index(index_name, composition, directory=directory)
        index_items = { item.ticker: item for item in index.items }

        self.actions = []

        balancer = Balancer(portfolio, index, params)
        actions_list, free_cash = balancer.calculate_actions()

        offers = self._collect_offers(actions_list, directory)
        positions = self._to_positions(
            balancer.calculated_positions, portfolio_items, index_items, offers, directory
        )

        return RebalancePreview(
            actions=self.actions,
            current_free_cash=portfolio.cash.to_float() if portfolio.cash else 0.0,
            free_cash=free_cash,
            positions=positions,
            index_date=index.date or None,
        )

    def _collect_offers(self, actions_list, directory) -> dict:
        """Действия балансировщика -> исполнимые Action + карта offer по тикеру.

        Ненайденные у брокера тикеры пропускаются с варнингом.
        Знак offer определяет направление: покупка > 0, продажа < 0.
        """
        offers = dict()
        for action in actions_list:
            share = self.broker.find_share(action.get("ticker"), "ticker", directory=directory)
            if share is None:
                logger.warning("Share %s not found, action skipped", action.get("ticker"))
                continue
            self.actions.append(Action(type=action.get("type"), quantity=action.get("quantity"), share=share))

            quantity = action.get("quantity")
            offers[share.ticker] = -quantity if action.get("type") == "SELL" else quantity
        return offers

    def _to_positions(
        self, calculated, portfolio_items, index_items, offers, directory
    ) -> list:
        """Расчётные позиции балансировщика -> позиции превью с весами и offer."""
        positions = []

        for position in calculated:

            portfolio_share = portfolio_items.get( position.ticker )

            index_share = index_items.get( position.ticker )

            uid = ""

            if portfolio_share:
                uid = portfolio_share.uid

            elif index_share:
                found_share = self.broker.find_share(position.ticker, "ticker", directory=directory)

                uid = found_share.uid if found_share is not None else ""

            positions.append(
                PortfolioPosition(
                    uid=uid,
                    ticker=position.ticker,
                    name=(
                        index_share.shortname
                        if index_share
                        else position.ticker
                    ),
                    index_weight=round(position.target_weight * 100, 2),
                    portfolio_weight=round(position.current_weight * 100, 2),
                    portfolio_count=position.balance,
                    offer=offers.get(position.ticker)
                )
            )

        return positions
