# 新增策略

策略放在 `ntquant/strategies/`。回测和研究共用
`ntquant/strategies/registry.py` 的注册表与配置构造函数。

1. 新建一个策略模块，定义继承 `BaseStrategyConfig` 的配置类和继承
   `BaseStrategy` 的策略类。自有参数用 msgspec 类型注解及默认值声明；
   `on_start()` 调用 `super().on_start()` 订阅 bar，再注册指标。
2. 在 `STRATEGIES` 中登记名称与 `(配置类, 策略类)`。可选地在 `ALIASES`
   添加简称。无需修改回测或研究的 runner。
3. 用终端选择策略并传参：

```bash
.venv/bin/python run.py backtest --strategy rsi_reversal --param period=7,oversold=25
```

配置文件也可在 `strategy.name` 指定策略，直接在 `strategy` 段写入它的参数。
切换 YAML 中的策略名时，应同步修改该段的专属参数；未知参数会报错。
命令行临时切换策略时，新策略采用其配置类默认值和 `--param` 覆盖值。

研究入口同样使用该注册表：

```bash
.venv/bin/python run.py research --strategy rsi_reversal --symbols BTC,ETH \
    --market perp --start 2023-01-01 --end 2024-01-01 --param period=7
```

`StrategyConfig` 子类需用类型注解声明字段；NautilusTrader 1.231.0 不支持
在该类中自定义 `__init__`/`__new__`。`strategy_id` 应传普通字符串。
