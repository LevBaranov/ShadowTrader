from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BalancerParams:
    """Параметры расчёта балансировки — настройки пользователя, не инсталляции.

    Раньше это была секция [balancer] в toml, общая для всех. Теперь у каждого
    параметра свой владелец в БД:

    * commission — тариф брокера (`users_broker.commission`): один для всех
      счетов и стратегий этого брокера;
    * delta, min_lots_to_keep, max_cash — свойства стратегии (`users_strategy`).

    delta и commission — доли, а не проценты: 0.05 = 5 %, 0.003 = 0,3 %.
    Проценты — только представление в UI и боте.
    """
    delta: Decimal
    commission: Decimal
    min_lots_to_keep: int
    max_cash: int = 0

    @classmethod
    def from_strategy(cls, strategy) -> "BalancerParams":
        """Собрать параметры по стратегии: комиссию берём с брокера её счёта."""
        return cls(
            delta=strategy.delta,
            commission=strategy.brokers_account.users_broker.commission,
            min_lots_to_keep=strategy.min_lots_to_keep,
            max_cash=strategy.max_cash,
        )
