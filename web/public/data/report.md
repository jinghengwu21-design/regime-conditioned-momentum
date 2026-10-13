# RCM-3F · 绩效与成本研究

**研究问题：** BTC 动量策略的历史表现有多稳健？提高交易成本后，收益和回撤如何变化？

运行：`20261013T130653Z-3efc448c` · 确定性研究 · 记录时间 2026-10-13T13:06:54.171884+00:00

资产：BTC/USDT:USDT；实际统计区间 [2020-01-01T00:00:00+00:00, 2026-10-03T12:05:00+00:00)，UTC。
单边手续费 5 bps，逐成交附加滑点 0 bps；平仓权益；资金费未计入。

历史账户呈现趋势获利与连续亏损交替的特征。评估重点是收益来源、已实现回撤和成交成本敏感性。[CALC-BASE]

## 可核验指标

| 指标 | 数值 | 证据 |
|---|---:|---|
| 交易笔数 | 922 | CALC-BASE → trades.csv / fills.csv |
| 累计收益 | 1681.58% | CALC-BASE → trades.csv / fills.csv |
| 复合年化收益 | 53.21% | CALC-BASE → trades.csv / fills.csv |
| 最大已实现回撤 | 30.09% | CALC-BASE → trades.csv / fills.csv |
| 每日账户收益 Sharpe | 1.245 | CALC-BASE → trades.csv / fills.csv |
| 盈利因子 PF | 1.409 | CALC-BASE → trades.csv / fills.csv |
| 胜率 | 25.16% | CALC-BASE → trades.csv / fills.csv |
| 期末权益 | 17,815.79 | CALC-BASE → trades.csv / fills.csv |
| 额外成本 | 0.00 | CALC-BASE → trades.csv / fills.csv |

## 研究发现

- 使用冻结交易账本重建账户权益，指标与原始记录逐项绑定。[E-BACKTEST]
- 成本情景覆盖入场、退出和盈利加仓；固定成交路径便于对照费用变化。[CALC-COST]
- 市场状态、突破确认与风险表达共同构成策略研究链路。[E-STRATEGY]

## 成本比较

固定成交与仓位路径，在每笔交易平仓时追加成本；包含全部进出场及加仓名义金额。

| 单边手续费 bps | 累计收益 | 已实现回撤 | 额外成本 USDT |
|---:|---:|---:|---:|
| 5 | 1681.58% | 30.09% | 0.00 |
| 8 | 1003.46% | 37.91% | 6,781.16 |
| 12 | 99.31% | 82.21% | 15,822.71 |

## 数据与计算口径

代码版本：`ledger-metrics-v1.0.0`；数据集：`rcm-3f-history-20261003-v1`。
CAGR 沿用原生有效回测区间的整数日数，365 日年化；Sharpe 由 UTC 每日账户收益计算，标准差使用 ddof=1。子区间起始权益承接原账户，按平仓时点选择交易。
成本敏感性不重新执行交易信号或仓位，不能解释为含延迟和市场冲击的重新回测。

- 行情附件截至 2026-10-03 00:00 UTC；回测账本截至当日 12:05 UTC，末尾半日行情未打包。
- 行情视图仅显示区间内完整 UTC 日；交易指标按原始时间边界计算。

## 独立复核

复核通过：True；指标 9 项；成本情景 3 组；纠错重跑：False。

## 证据索引

| 编号 | 来源 | 定位 |
|---|---|---|
| E-BACKTEST | RCM-3F 连续历史回测 | research/operations/v3f_full_history_2026-10-03/REPORT_CN.md |
| E-METRICS | 账户收益与成本核验口径 | research_agent/metrics.py + audit.py |
| E-STRATEGY | 动量研究规则与风险表达 | user_data/strategies/SarkazV3F.py; research/operations/v3f_original_oos_resume_2026-10-03/MARKET_ACHIEVEMENTS.md |
| E-ENGINEERING | 原交易系统的工程模块 | WORKSPACE_ASSET_MAP.md; scripts/maintenance/build_freqtrade_dryrun_stack.py; deployments/dryrun-telegram-monitor/ftdry.py |
| E-CONTEXT | 研究上下文与实验身份 | research/chronicle.json; docs/AGENT_RESEARCH.md |
| CALC-BASE | 账户指标计算 | result.json → base；trace.jsonl → calculate_metrics |
| CALC-COST | 成交成本情景 | result.json → costs；trace.jsonl → compare_costs |
| E-MARKET | OKX 历史行情附件 | market_daily.csv；manifest.json → market_sources |

所有公开演示轨迹均保留生成时间与运行模式；离线报告由确定性模板组织，模型模式由 LLM 生成定性分析并经过同一复核门禁。