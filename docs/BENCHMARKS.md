# 设计与研究系统参考

RCM 的信息结构围绕策略研究展开：先解释问题和研究过程，再提供保留策略、失败档案、账户分析及工程运行。参考项目分别贡献金融信息组织、交互模式和研究循环的方法，应用代码独立实现。

审阅日期：2026-10-13。

| 参考 | 审阅材料 | 在 RCM 中的应用 |
|---|---|---|
| [Wealthfolio](https://github.com/wealthfolio/wealthfolio) | [产品界面](https://wealthfolio.app)中的账户、曲线、明细与金融信息层级 | 浅色纸面、低对比网格、清晰数值与细分隔线；权益图附单位和口径 |
| [shadcn/ui](https://github.com/shadcn-ui/ui) | [Dashboard 示例](https://ui.shadcn.com/examples/dashboard)的表格、筛选、选择与操作布局 | 研究档案的组合筛选、清楚的选择状态、双研究比较、轻量对话框 |
| [Microsoft RD-Agent](https://github.com/microsoft/RD-Agent) | [项目说明](https://github.com/microsoft/RD-Agent/blob/main/README.md)中的 research／development 分工与因子—模型迭代 | 将问题、规格、实现、实验、反馈和研究记忆串成可逐阶段阅读的循环 |
| [QuantStats](https://github.com/ranaroussi/quantstats) | `stats.py` 中月度收益、滚动 Sharpe、回撤片段和报告结构 | 完整账户附件：权益、市场参照、underwater、月度复合收益与恢复时间 |
| [OpenBB Workspace](https://github.com/OpenBB-finance/workspace) | 归档项目的 React 工作区与指标组件 | 统一分析区间、度量口径和可下钻工作区 |
| [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) | 桌面架构、pipeline 与叙述数值绑定 | 计算、叙述、独立复核分层；保留原结论与修正轨迹 |

Wealthfolio、shadcn/ui 和 RD-Agent 分别提供成熟金融产品、广泛使用的界面组件和研究自动化的参考视角。采用它们的信息与交互思想，没有搬运品牌、截图或项目绩效。

## 信息与视觉取舍

**研究过程作为首页。** 首屏陈述条件动量问题，并显示保留策略的真实账户曲线。下面按执行基线、规则形成、扩展反证和持续复核组织阅读。

**把失败当作研究资料。** 48 个节点都有问题、方法、结果和裁决。档案可以按家族、状态和文本组合过滤，可以把两项研究并排比较并导出结果。

**用不同版式表达不同材料。** 首页使用长文式布局，机制使用展开条目，实验过程使用阶段导航，账户采用图表与表格。页间共享字体、间距、细线和颜色语义。

**颜色服务金融含义。** 深灰文字、蓝灰操作、低饱和绿色曲线；收益、损失和研究裁决同时附有文字或符号。自托管 Inter 与 IBM Plex Mono 用于界面和数值，Georgia 用于少量标题。

**来源保持可读。** 研究编号、报告路径、样本窗口、费用与版本足以定位结果。代码目录、数据清单和调用轨迹提供工程细节。

依赖许可见 [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md)。参考项目不是运行时依赖；Wealthfolio 的 AGPL 代码未纳入本仓库。
