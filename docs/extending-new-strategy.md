# 扩展一个新策略

本指南带你用 ntquant 脚手架新增一个策略，从定义到跑回测。核心思路：**策略只关心自己的
指标与下单逻辑**，引擎、配置、数据、报表的复杂度已由公共层（`strategies/base.py`、
`backtest/runner.py`、`config.py`）处理。

> **前置必读**：先看 [AGENTS.md](../AGENTS.md) 的「版本铁律」与 [version-notes.md](version-notes.md)
> 的「已知坑」。1.231.0 的 `StrategyConfig` 扩展**不能**用官方示例的
> `__init__`/`__new__` + `_CUSTOM_FIELDS`（报 `Struct types cannot define __init__`），
> 必须用 **msgspec 类型注解**字段。

## 约定速览

- 配置类：继承 `BaseStrategyConfig`，用**类型注解**声明自有字段（会有默认值）。
- 策略类：继承 `BaseStrategy`，在 `__init__` 里初始化指标，在 `on_start`/`on_bar`(或
  `on_quote`/`on_trade`) 里实现逻辑。
- 下单：调用基类 `self.submit_market(side, size)`，内部会用 `instrument.make_qty()`
  把 `size` 规范到 `size_precision`，避免数量精度报错。
- `strategy_id` 用**普通字符串**（如 `"RSI-001"`），不要传 `StrategyId(...)` 对象。
- 每次回测实例需唯一 `strategy_id`；多策略并行时建议同时设置 `order_id_tag`。

## 步骤一：新增策略模块

在 `ntquant/strategies/` 下新建文件，例如 `rsi_reversal.py`。以 EMA 交叉为模板
（本例使用 1.231.0 的真实指标类 `RelativeStrengthIndex`；注意它**没有**内置的
`oversold`/`overbought` 阈值字段，阈值由你的配置类提供）：

```python
from nautilus_trader.indicators import RelativeStrengthIndex
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide

from ntquant.strategies.base import BaseStrategy, BaseStrategyConfig


class RSIReversalConfig(BaseStrategyConfig):
    """Config for an RSI mean-reversion strategy (msgspec-annotated fields)."""

    rsi_period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0


class RSIReversalStrategy(BaseStrategy):
    """Enter long when RSI is oversold, exit/short when overbought."""

    def __init__(self, config: RSIReversalConfig) -> None:
        super().__init__(config)
        self.rsi = RelativeStrengthIndex(config.rsi_period)

    def on_start(self) -> None:
        """Register the RSI indicator and subscribe to bars."""
        super().on_start()
        if self.instrument is None:
            return
        self.register_indicator_for_bars(self.config.bar_type, self.rsi)
        self.log.info("RSI Reversal strategy initiated")

    def on_bar(self, bar: Bar) -> None:
        if not self.indicators_initialized():
            return

        instrument_id = self.config.instrument_id
        rsi = self.rsi.value

        if rsi <= self.config.oversold and self.portfolio.is_flat(instrument_id):
            self.log.info(f"RSI oversold ({rsi:.2f}) -> BUY")
            self.submit_market(OrderSide.BUY, self.config.trade_size)
        elif rsi >= self.config.overbought and self.portfolio.is_net_long(instrument_id):
            self.log.info(f"RSI overbought ({rsi:.2f}) -> SELL")
            self.submit_market(OrderSide.SELL, self.config.trade_size)
```

### 可用的数据回调

策略可任意实现下列回调（按事件分派）：

- 数据：`on_bar(Bar)`、`on_quote(QuoteTick)`、`on_trade(TradeTick)`、`on_mark_price(...)` 等。
- 订单：`on_order_filled(event)`、`on_order_rejected(event)`、`on_order_event(event)` 等。
- 持仓：`on_position_opened(event)`、`on_position_closed(event)`、`on_position_event(event)` 等。
- 生命周期：`on_start()`、`on_stop()`、`on_resume()`、`on_dispose()`。

## 步骤二：接入 runner 注册表

`ntquant/backtest/runner.py` 用 `STRATEGY_CONFIGS` 和 `make_strategy` 决定跑哪个策略。
新增两处：

1. 在文件顶部的 `STRATEGY_CONFIGS` 里登记配置类：

```python
from ntquant.strategies.rsi_reversal import RSIReversalConfig, RSIReversalStrategy

STRATEGY_CONFIGS = {
    "ema_cross": EMACrossConfig,
    "rsi_reversal": RSIReversalConfig,   # 新增
}
```

2. 在 `make_strategy(config)` 里补上构建分支（按策略名返回 strategy 实例）：

```python
    if name == "ema_cross":
        return EMACrossStrategy(cfg)
    if name == "rsi_reversal":
        return RSIReversalStrategy(cfg)   # 新增
    raise NotImplementedError(...)
```

注意：`make_strategy` 会把 `config.strategy`（frozen dataclass）里的
`fast_period`/`slow_period` 等参数传给配置类；若你的策略需要独有参数，见下一步。

## 步骤三：把参数写进配置

`ntquant/config.py` 的 `StrategyConfig` 是承载策略参数的 frozen dataclass。
给新策略加字段（如 `rsi_period`、`oversold`、`overbought`）：

```python
@dataclass(frozen=True)
class StrategyConfig:
    name: str = "ema_cross"
    strategy_id: str = "EMA-001"
    trade_size: str = "10000"
    fast_period: int = 10
    slow_period: int = 30
    bar_type: str = "EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL"
    rsi_period: int = 14          # 新增
    oversold: float = 30.0        # 新增
    overbought: float = 70.0      # 新增
```

然后在 `ntquant/configs/backtest.yaml` 的 `strategy` 节加默认值（或用 `.env` 覆盖）：

```yaml
strategy:
  name: rsi_reversal
  strategy_id: RSI-001
  trade_size: "10000"
  rsi_period: 14
  oversold: 30
  overbought: 70
  bar_type: EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL
```

## 步骤四：写测试

在 `tests/` 新建 `test_rsi_reversal.py`，覆盖「配置可构造」与「策略可实例化」两条关键路径：

```python
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId
from ntquant.strategies.rsi_reversal import RSIReversalConfig, RSIReversalStrategy


def test_rsi_config_constructible():
    cfg = RSIReversalConfig(
        instrument_id=InstrumentId.from_str("EUR/USD.SIM"),
        bar_type=BarType.from_str("EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL"),
        trade_size="10000",
        rsi_period=14,
        oversold=30.0,
        overbought=70.0,
        strategy_id="RSI-001",
    )
    assert cfg.rsi_period == 14


def test_rsi_strategy_instantiates():
    cfg = RSIReversalConfig(
        instrument_id=InstrumentId.from_str("EUR/USD.SIM"),
        bar_type=BarType.from_str("EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL"),
        trade_size="10000",
        strategy_id="RSI-001",
    )
    assert isinstance(RSIReversalStrategy(cfg), RSIReversalStrategy)
```

## 步骤五：运行与验证

```bash
make backtest   # 跑配置里指定的策略（backtest.yaml 的 strategy.name）
make test       # pytest tests/
make report     # CSV + 交互式 tearsheet
```

## 多个策略并行

- 每个实例用**唯一** `strategy_id`（如 `RSI-001`、`EMA-002`）。
- 可通过 `order_id_tag` 让订单 ID 前缀唯一（`StrategyConfig(order_id_tag="RSI")`）。
- 在同一 `BacktestEngine` 上 `add_strategy` 多个实例即可；注意 `strategy_id` 不能重复。
