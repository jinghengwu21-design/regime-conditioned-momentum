# Regime-Conditioned Momentum

**条件动量策略研究 · 因子实验档案 · Agent 研究流程**

A systematic research project on BTC momentum: from failed hypotheses and execution audits to a retained, regime-conditioned strategy.

[研究网站](https://jinghengwu21-design.github.io/regime-conditioned-momentum/) · [研究全史](docs/RESEARCH_HISTORY.md) · [保留策略](docs/STRATEGY.md) · [48 个研究节点](research/README.md) · [Agent 方法](docs/AGENT_RESEARCH.md)

[![Research acceptance](https://github.com/jinghengwu21-design/regime-conditioned-momentum/actions/workflows/check.yml/badge.svg)](https://github.com/jinghengwu21-design/regime-conditioned-momentum/actions/workflows/check.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-486b5b.svg)](LICENSE)

![RCM 研究首页](docs/screenshots/overview.png)

RCM 研究一个具体问题：**异常上涨在什么市场背景下具有延续性，以及怎样把这种差异转化为可执行的风险暴露。**

研究经历了 RLRS 的成交审计、M / K / N 系列和 PA5M 的失败、Signal K 事件定义、Bayes 条件筛选、有限仓位权重、盈利加仓、状态模型与微观结构因子。最终保留 RCM-3F：BTC 永续、5 分钟、单向做多，用市场状态、结构突破、异常成交量和有限风险配置表达条件动量。

## 从哪里开始

| 入口 | 内容 |
|---|---|
| [研究过程](docs/RESEARCH_HISTORY.md) | 七个阶段串起早期失败、保留策略、因子替代与执行反馈 |
| [研究档案](research/README.md) | 48 个决策节点，12 个研究家族；问题、方法、结果、裁决与来源 |
| [策略规格](docs/STRATEGY.md) | 六个实际机制、权重表、RCM-3 / 3F 对照和代码入口 |
| [Agent 研究方法](docs/AGENT_RESEARCH.md) | 研究者与 Agent 的分工、四轮实验、讨论如何改变下一轮设计 |
| [工程实现](docs/ENGINEERING.md) | 原生执行研究、账户计算、分析 Agent、独立复核与故障注入 |

网站提供研究搜索、家族／裁决筛选、双研究比较、逐阶段实验阅读、版本窗口切换，以及账户、成本和逐笔成交下钻。

## 几个决定研究方向的结果

- **成交语义改变结论。** RLRS 的原始曲线存在大量不可成交价格；修正后的 233 笔为 −46.80%，研究转向原生执行与逐笔对照。[R01](research/notes/R01.md)
- **更多条件未必增加信息。** EMA 与 Donchian 的组合给出相同交易；同 K TFI 正值保留 99.65% 的条件事件，未能替代异常成交量。[R08](research/notes/R08.md)、[R41](research/notes/R41.md)
- **弱确认仍包含重要机会。** 历史归因中 clean low-confirm 的 160 笔 PF 为 1.949，支持有限权重表达而非整体删除。[R13](research/notes/R13.md)
- **模型指标与交易指标分开评价。** XGBoost 复刻规则教师的 accuracy 约 94.63%，替换过滤后交易与收益却下降，最终保留规则状态。[R23](research/notes/R23.md)
- **风险预算不创造新信号。** RCM-3F 在相同的 510 笔历史交易上，把 CAGR 从 31.00% 提高到 46.44%，回撤也从 20.95% 提高到 30.09%。[R16](research/notes/R16.md)

## 保留策略

```text
Signal K + 异常量
    → Regime V2 + 结构位置
    → 下一完整收盘观察
    → 五档 stake / leverage 权重
    → +1R 单次加仓 + 原入场价保本
    → 前 4h 低点跟踪 / 24h 上限
```

下一收盘的强弱决定权重，弱确认仍可交易。动态 Bayes 门槛、XGBoost 状态、HighAdd50 和二次信号加仓保留在研究档案中。历史类名与研究名称的映射见 [策略代码](strategy/README.md)。

| 连续历史 | CAGR | 日账户 Sharpe | 最大已实现回撤 | 期末权益 |
|---|---:|---:|---:|---:|
| 922 笔交易 / 2,247 条成交 | 53.21% | 1.245 | 30.09% | 17,815.79 USDT |

有效回测区间为 2020-01-04 11:20 至 2026-10-03 12:00 UTC。初始账户 1,000 USDT；单边手续费 5 bps；资金费未计；按平仓确认损益，跨年不重置。2024 年以后包含策略开发与后续观察；历史检验窗口也被后来的研究复用。

2026 年归档区间收益约 **+0.55%**。在固定成交路径上把单边费用提高到 8 bps，期末权益变为 **11,034.63 USDT**。这些结果与右尾依赖一起，是后续研究的起点。

## 快速开始

Python 3.11–3.14、Node.js 22.12+ 或 24、npm。

```bash
git clone https://github.com/jinghengwu21-design/regime-conditioned-momentum.git
cd regime-conditioned-momentum
```

Windows：

```powershell
powershell -NoProfile -File .\scripts\start.ps1
```

macOS / Linux：

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
npm --prefix web ci
npm --prefix web run build
python -m research_agent.server
```

打开 [本地研究站](http://127.0.0.1:8507)。GitHub Pages 使用公开数据和运行记录；本地服务提供新的分析执行。网站和报告重算使用仓库内账本；原始 5m 信号回测使用 Freqtrade 环境及对应行情。

## 分析 Agent

```bash
python -m research_agent.cli demo
python -m research_agent.cli run --scenario numeric_mismatch
python -m research_agent.cli evaluate
```

LangGraph 执行规划、上下文、工具分析、独立复核、修正与报告。六个工具读取行情覆盖、回测、账户指标、成本情景和研究证据。五类录制实验涵盖基准、数值偏差、外部指令注入、行情缺口和工具越权。

本地模型模式通过服务端 `OPENAI_API_KEY` 和 `OPENAI_MODEL` 配置：

```bash
python -m research_agent.cli run --mode openai
```

公开记录采用确定性执行；模型接口测试使用真实 SDK 与模拟 HTTP 响应。历史策略探索中的研究者／Agent 循环记录在 [Agent 方法](docs/AGENT_RESEARCH.md)，分析服务的代码在 [research_agent/](research_agent/)。

## 维护与复现

```bash
python scripts/build_research.py
python scripts/build_terminal.py
python -m pytest tests
python scripts/verify_strategy.py
npm --prefix web test
npm --prefix web run build
```

`research/chronicle.json` 与 `research/INTRO.md` 维护研究内容，构建为网站数据、CSV、独立笔记和研究长文。`data/` 保存交易、成交、日线附件与指标定义。`web/` 使用 React、TypeScript 和 ECharts；Python 负责计算与 Agent 运行。

[验证记录](docs/VERIFICATION.md) · [架构](docs/ARCHITECTURE.md) · [设计参考](docs/BENCHMARKS.md) · [版本记录](CHANGELOG.md) · [第三方许可](THIRD_PARTY_NOTICES.md)
