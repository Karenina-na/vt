# 因子开发指南

研究层 `ntquant/research/` 是独立模块，**不修改脚手架核心**（`config.py` / `backtest/runner.py`
/ `backtest/parameters.py`）。「因子 = 标准 Nautilus Strategy 子类」——新增一个因子只需 3 步，
无需碰核心代码。

已内置 5 个经典因子（`ntquant/strategies/`）：

| 因子名 | 类型 | 信号 | 关键字 |
|---|---|---|---|
| `ema_cross` | 趋势 | 快慢 EMA 金叉/死叉 | `fast_period`, `slow_period` |
| `rsi_reversal` | 均值回归 | 超卖买入 / 超买卖出 | `period`, `oversold`, `overbought` |
| `bollinger_reversal` | 均值回归 | 收盘破下轨买/破上轨卖 | `period`, `num_std` |
| `roc_momentum` | 动量 | ROC 超阈做多/做空 | `period`, `entry_threshold` |
| `macd_cross` | 动量 | MACD 信号线零轴穿越 | `fast_period`, `slow_period`, `signal_period` |

## 使用

```bash
# 选定因子 × 品种 × 时间窗，跑完固定六项（PnL/收益%/胜率/盈亏比/夏普/回撤）
.venv/bin/python run.py research \
    --strategy rsi_reversal --symbols BTC,ETH,SOL \
    --market perp --start 2023-01-01 --end 2024-01-01

# 覆盖因子参数（k=v,k2=v2）
.venv/bin/python run.py research --strategy rsi_reversal --symbols BTC \
    --market perp --start 2023-01-01 --end 2024-01-01 \
    --param period=7,oversold=25
```

## 新增一个因子（3 步）

### 第 1 步：写策略子类 `ntquant/strategies/<name>.py`
继承 `BaseStrategy`/`BaseStrategyConfig`（见 `ntquant/strategies/rsi_reversal.py`）：

```python
from nautilus_trader.indicators import RelativeStrengthIndex
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide
from ntquant.strategies.base import BaseStrategy, BaseStrategyConfig

class RsiReversalConfig(BaseStrategyConfig):
    period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0

class RsiReversalStrategy(BaseStrategy):
    def __init__(self, config: RsiReversalConfig) -> None:
        super().__init__(config)
        self.rsi = RelativeStrengthIndex(config.period)

    def on_start(self) -> None:
        super().on_start()
        if self.instrument is None:
            return
        self.register_indicator_for_bars(self.config.bar_type, self.rsi)

    def on_bar(self, bar: Bar) -> None:
        if not self.indicators_initialized():
            return
        iid = self.config.instrument_id
        rsi = self.rsi.value
        if self.portfolio.is_flat(iid):
            if rsi < self.config.oversold:
                self.submit_market(OrderSide.BUY, self.config.trade_size)
            elif rsi > self.config.overbought:
                self.submit_market(OrderSide.SELL, self.config.trade_size)
```

要点：
- `Config` 用 **msgspec 类型注解字段**声明自有参数（不要用 `__init__`+`_CUSTOM_FIELDS`，1.231.0 报错）。
- `BaseStrategy` 的 `submit_market(side, size)` 已处理数量精度；`on_start` 里 `super().on_start()` 会订阅 bars。
- 下单前用 `self.indicators_initialized()` 做预热保护，用 `self.portfolio.is_flat(iid)` 判断空仓。

### 第 2 步：注册进 `ntquant/research/factors.py`
在 `FACTORY_CONFIGS`（Config 类）、`FACTOR_BUILDERS`（Strategy 类）、`DEFAULT_PARAMS`（默认参数）
各加一行；可选在 `ALIASES` 加别名。

### 第 3 步：跑研究
`python run.py research --strategy <你的因子名> ...`。`research/runner.py` 通过
`build_factor` 反射式填充因子字段，**无需**改 `make_strategy`。

## 常用指标（1.231.0 实测可用）
`ExponentialMovingAverage`、`SimpleMovingAverage`、`RelativeStrengthIndex`、`BollingerBands`、
`RateOfChange`、`AverageTrueRange`、`MovingAverageConvergenceDivergence`、`VolumeWeightedAveragePrice`
等（见 `nautilus_trader.indicators`）。

> 已知坑：1.231.0 的 `MovingAverageConvergenceDivergence` **内部 signal EMA 未构造**，
> 直接 `update_raw` 会抛 `AttributeError: 'NoneType' object has no attribute 'update_raw'`。
> `macd_cross` 因子因此**自建** MACD = 快 EMA − 慢 EMA，再对 MACD 线喂一条 EMA 当信号线。
> 新增 MACD 类因子请沿用此自建方案。

## 因子参数注入流程
```
run.py research --strategy <factor> --param a=1,b=2
  -> research/runner.run_factor_evaluation
  -> build_factor(factor, config, params)
  -> 复制 config.strategy 的共享字段 + DEFAULT_PARAMS/<params> 中的因子字段
  -> FactorConfig(**kwargs) -> FactorStrategy
```
Shared 字段（instrument_id / bar_type / trade_size / strategy_id）自动从 `config` 注入；
因子自有字段由 `--param` 或 `DEFAULT_PARAMS` 提供。
