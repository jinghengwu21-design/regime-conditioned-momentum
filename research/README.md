# 研究档案

Regime-Conditioned Momentum 的研究节点、源文档目录与方法综述。

[完整研究过程](../docs/RESEARCH_HISTORY.md) · [策略规格](../docs/STRATEGY.md) · [Agent 研究方法](../docs/AGENT_RESEARCH.md)

`chronicle.json` 是决策档案的数据源；`INTRO.md` 是研究综述；`notes/`、CSV 和网站数据由 `python scripts/build_research.py` 生成。`source-catalog.json` 保留 2026-10-03 原研究工作区的文档目录，包含历史副本。目录条目与独立实验数量不同。

| 编号 | 研究节点 | 家族 | 裁决 |
|---|---|---|---|
| R01 | [RLRS：先修正成交语义](notes/R01.md) | 早期探索 | 淘汰 |
| R02 | [M 系列：独立优势与仓位竞争](notes/R02.md) | 早期探索 | 淘汰 |
| R03 | [M14：开发窗优势未能迁移](notes/R03.md) | 早期探索 | 淘汰 |
| R04 | [PA5M：频率目标不等于正期望](notes/R04.md) | 早期探索 | 淘汰 |
| R05 | [K 系列：时段拍卖的最终复盘](notes/R05.md) | 早期探索 | 淘汰 |
| R06 | [N-series：强制流与数据语义](notes/R06.md) | 早期探索 | 暂缓 |
| R07 | [Signal K：强实体的第一轮检验](notes/R07.md) | 信号形成 | 淘汰 |
| R08 | [EMA × Donchian：检查信息重叠](notes/R08.md) | 信号形成 | 淘汰 |
| R09 | [波动扩张：机制合理还需要迁移](notes/R09.md) | 信号形成 | 淘汰 |
| R10 | [异常成交参与：从形态到事件](notes/R10.md) | 信号形成 | 保留 |
| R11 | [Bayes：筛选概率与实际增量](notes/R11.md) | 信号形成 | 研究保留 |
| R12 | [Next-close：先看接受，再承担暴露](notes/R12.md) | 信号形成 | 保留 |
| R13 | [有限权重：保留机会，分配风险](notes/R13.md) | 风险表达 | 保留 |
| R14 | [+1R 加仓与原始入场锚](notes/R14.md) | 风险表达 | 保留 |
| R15 | [POC、提早退出与右尾损失](notes/R15.md) | 风险表达 | 淘汰 |
| R16 | [RCM-3 → RCM-3F：固定信号，放大预算](notes/R16.md) | 风险表达 | 保留 |
| R17 | [HighAdd50：右尾增配未换来历史优势](notes/R17.md) | 风险表达 | 淘汰 |
| R18 | [第二次信号加仓与保证金预留](notes/R18.md) | 风险表达 | 淘汰 |
| R19 | [ETH：相同规则的迁移研究](notes/R19.md) | 跨资产与方向 | 研究保留 |
| R20 | [Kazdel：空头收益的集中性](notes/R20.md) | 跨资产与方向 | 淘汰 |
| R21 | [G1：上方接受失败与下方接受](notes/R21.md) | 跨资产与方向 | 研究保留 |
| R22 | [C1：多空组合与暴露拆解](notes/R22.md) | 跨资产与方向 | 研究保留 |
| R23 | [XGBoost：规则教师一致率](notes/R23.md) | 模型研究 | 研究保留 |
| R24 | [GMM × XGBoost：潜在状态与滚动推断](notes/R24.md) | 模型研究 | 研究保留 |
| R25 | [右尾、费用与漏单敏感性](notes/R25.md) | 稳健性 | 研究保留 |
| R26 | [删除 Regime：更多交易是否更好](notes/R26.md) | 因子复核 | 保留 |
| R27 | [V4F：状态规则数值化](notes/R27.md) | 因子复核 | 淘汰 |
| R28 | [Signal K 数值校准](notes/R28.md) | 因子复核 | 淘汰 |
| R29 | [路径效率与传统动量替换](notes/R29.md) | 因子复核 | 淘汰 |
| R30 | [季节成交量：活跃度与异常参与](notes/R30.md) | 因子复核 | 淘汰 |
| R31 | [TSMOM × 实现波动](notes/R31.md) | 因子复核 | 淘汰 |
| R32 | [Signal K 的 1m 路径](notes/R32.md) | 因子复核 | 淘汰 |
| R33 | [Statistical Jump Model](notes/R33.md) | 模型研究 | 淘汰 |
| R34 | [经典独立动量](notes/R34.md) | 独立路线 | 淘汰 |
| R35 | [固定时钟日内动量](notes/R35.md) | 独立路线 | 淘汰 |
| R36 | [VWAP 均值回归](notes/R36.md) | 独立路线 | 淘汰 |
| R37 | [J8 波动扩张突破](notes/R37.md) | 独立路线 | 淘汰 |
| R38 | [永续／指数 basis impulse](notes/R38.md) | 独立路线 | 淘汰 |
| R39 | [负向小时冲击反转](notes/R39.md) | 独立路线 | 淘汰 |
| R40 | [OI：持仓创建与方向](notes/R40.md) | 数据与微观结构 | 淘汰 |
| R41 | [TFI：主动买入是否新增信息](notes/R41.md) | 数据与微观结构 | 淘汰 |
| R42 | [OBV：慢状态与短期启动](notes/R42.md) | 因子复核 | 淘汰 |
| R43 | [Volume Profile：先检验数据表达](notes/R43.md) | 数据与微观结构 | 淘汰 |
| R44 | [CUSUM：信息时钟的采样问题](notes/R44.md) | 数据与微观结构 | 淘汰 |
| R45 | [秒级订单流、Lead-lag 与宏观状态](notes/R45.md) | 外部前沿 | 暂缓 |
| R46 | [信号、漏单与重复加仓](notes/R46.md) | 工程落地 | 研究保留 |
| R47 | [原生 Freqtrade 双容器研究栈](notes/R47.md) | 工程落地 | 保留 |
| R48 | [固定策略延长到完整历史](notes/R48.md) | 持续复核 | 保留 |
