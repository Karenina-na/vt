# ntquant

个人量化投研与回测脚手架，基于 **NautilusTrader** 的**事件驱动、回测/生产同构**架构构建。
面向个人使用场景，把「数据 → 策略 → 回测 → 分析」标准化为可复用、可扩展的一套骨架，
让验证策略思路、比较参数、生成研报的过程尽量少写样板代码。

> **版本注意**：仓库锁定 `nautilus_trader==1.231.0`。官方 `latest` 文档的部分导入路径
> 与 1.231.0 **不一致**，本项目一律以实测可用的路径为准，映射与坑见
> [docs/version-notes.md](docs/version-notes.md)。

## 项目背景

- **现状**：官方示例往往散落在单文件脚本里，参数硬编码、数据用内存随机、缺少统一配置与报表。
  换个策略或数据就要重写一遍引擎搭建逻辑。
- **目标**：沉淀一个「最小可用」的脚手架 —— 引擎/配置/数据/报表的复杂度下沉到公共层，
  策略层只写自己关心的指标与下单逻辑；回测、调参、出报告一条命令行完成。
- **范围**：回测 + 投研；实盘 `live/` 仅占位（预留二期接入 `LiveNode` + adapter）。
- **设计原则**：沿用 Nautilus 官方 `Strategy/St`rategyConfig/BacktestEngine/ReportProvider`
  等概念，尊重其 domain model，但在导入路径、配置方式上全部以 1.231.0 **实测**为准。

## 功能特性

- **策略底座**：`BaseStrategyConfig`/`BaseStrategy` 提供指标注册、下单封装、数量精度规范化、
  停止时清仓的公共逻辑；新策略只需继承并实现核心回调。
- **示例策略**：`EMACrossStrategy` 双均线交叉（金叉/死叉 + 空翻多、多翻空），可直接运行。
- **数据层**：合成 OHLCV 生成器 + `ParquetDataCatalog` 读写封装（写库/读取/列出标的），
  并预留真实数据下载接口 `loaders.py`。
- **回测引擎**：封装低层 `BacktestEngine`，自动构建 SIM venue / instrument / 策略 / 数据，
  收集订单、成交、持仓、账户四大报表与绩效统计。
- **参数扫描**：零依赖 `itertools` 网格搜索，自动聚合 PnL / 胜率 / 期望 / 夏普等指标成表。
- **分析与可视化**：`ReportProvider` CSV 报表 + `performance_summary` 绩效摘要 +
  交互式 Plotly HTML tearsheet（净值/回撤/月度收益等）。
- **风控工具**：按账户风险计算仓位、`RiskEngineConfig` 工厂（含 1.231.0 bug 规避）。
- **工程化**：YAML + `.env` 类型化配置、argparse CLI、`Makefile` 任务入口、pytest 单测。

## 安装

Python 3.12 + `uv`：

```bash
make init       # 从 .env.example 复制 .env（密钥/覆盖项）
make install    # uv 安装项目 + dev 依赖到 .venv
```

## 快速开始

### 1. 单次回测（CLI）

```bash
make backtest
```

等价于：

```bash
.venv/bin/python -m ntquant.cli backtest
```

运行 EMA 交叉回测，打印 PnL，并在 `output/` 生成 `run_{orders,fills,positions,account}.csv`。
可选项：`--catalog`（从数据目录加载 bars）、`--config <yaml>`、`--prefix <name>`。

### 2. 参数扫描（CLI）

```bash
make param
```

在 `ntquant/configs/param.yaml` 定义扫描网格（如 `fast_period`、`slow_period`、`trade_size`），
输出 `output/param_results.csv` 并打印各组合的绩效对比。

### 3. 报表 + 交互式图表（CLI）

```bash
make report
```

生成全部 CSV 报表与交互式 `output/tearsheet.html`（Plotly）。

### 4. 运行测试

```bash
make test   # pytest tests/，10 用例全过
```

## Python API 示例

```python
from ntquant.config import load_backtest_config
from ntquant.backtest.runner import run_backtest
from ntquant.analysis.stats import performance_summary
from ntquant.analysis.visuals import make_tearsheet

cfg = load_backtest_config("ntquant/configs/backtest.yaml")
outcome = run_backtest(cfg)                 # use_catalog=True 可读取数据目录
print(performance_summary(outcome))         # PnL/胜率/期望/夏普等
make_tearsheet(outcome, "output/tearsheet.html")

# 数据目录读写
from ntquant.data.catalog import DataCatalog
from ntquant.data.synthetic import generate_synthetic_bars
from ntquant.backtest.instruments import make_bar_type
bt = make_bar_type("EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL")
cat = DataCatalog("docs/data")
cat.write_bars(generate_synthetic_bars(bt, count=1000, seed=42))

# 风控：按账户风险算持仓
from ntquant.risk import position_size_from_risk
size = position_size_from_risk(100000, "1.0850", "1.0800", "0.01")  # 1% 风险 -> 200000
```

## 配置

- **`ntquant/configs/backtest.yaml`**：单次回测的 venue / instrument / strategy / data 参数。
- **`ntquant/configs/param.yaml`**：参数扫描网格 + data 设置。
- **`.env`**：密钥与覆盖项，格式为 `NTA_<SECTION>__<KEY>=<value>`，例如
  `NTA_STRATEGY__FAST_PERIOD=15`，会覆盖对应 YAML 项。

## 目录结构

```
vt/
├── pyproject.toml          # 依赖与包元数据（锁定 1.231.0）
├── Makefile                # 常用任务入口
├── AGENTS.md               # 项目结构与约定（改动前必读）
├── README.md               # 本文档
├── docs/
│   ├── version-notes.md            # Nautilus 1.231.0 实测路径映射与已知坑
│   ├── extending-new-strategy.md   # 如何新增一个策略
│   └── supported-instruments.md    # 支持的金融产品与配置
├── ntquant/
│   ├── config.py           # 类型化配置加载（YAML + NTA_* 环境变量）
│   ├── cli.py              # CLI: backtest / param / report
│   ├── logging.py          # 统一日志
│   ├── configs/            # backtest.yaml / param.yaml
│   ├── data/               # synthetic(合成) / catalog(Parquet) / loaders(占位)
│   ├── strategies/         # base 底座 + ema_cross 示例
│   ├── backtest/           # runner / parameters / instruments(资产分派)
│   ├── analysis/           # reports / stats / tearsheet
│   ├── risk/               # 风控（仓位 + RiskEngineConfig）
│   └── live/               # 实盘占位
└── tests/                  # pytest 单测
```

## 相关文档

- [AGENTS.md](AGENTS.md) — 项目结构与约定（改动前必读）
- [docs/version-notes.md](docs/version-notes.md) — Nautilus 1.231.0 实测路径与已知坑
- [docs/extending-new-strategy.md](docs/extending-new-strategy.md) — 如何新增一个策略
- [docs/supported-instruments.md](docs/supported-instruments.md) — 支持的金融产品与配置
