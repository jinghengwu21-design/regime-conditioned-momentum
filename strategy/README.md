# Strategy source

RCM-3F（Regime-Conditioned Momentum, revision 3F）的历史研究类名为 `SarkazV3F`。`frozen/` 保存 19 个策略及依赖文件；`manifest.json` 记录来源类、快照日期和文件目录。旧类名和入场标签保留为研究沿革，当前项目使用 RCM 名称。

## 阅读顺序

1. [SarkazV3F.py](frozen/user_data/strategies/SarkazV3F.py)：RCM-3F 的最终 1.50 倍风险预算。
2. [SarkazV3.py](frozen/user_data/strategies/SarkazV3.py)：OriginalBE 与首仓参考。
3. [SarkazAddonProbes.py](frozen/user_data/strategies/SarkazAddonProbes.py)：盈利加仓与资本预留。
4. [SarkazCompositeProbes.py](frozen/user_data/strategies/SarkazCompositeProbes.py)：有限仓位权重。
5. [SarkazFollowthroughProbes.py](frozen/user_data/strategies/SarkazFollowthroughProbes.py)：下一收盘强弱与 Fresh。
6. [BtcNextCloseBayesLongV1Strategy.py](frozen/user_data/strategies/BtcNextCloseBayesLongV1Strategy.py)：入场候选、时点和初始风险上下文。
7. [研究特征代码](frozen/scripts/research/)：Signal K、结构与 Regime V2。

历史文件包含共同开发阶段的其他候选类。最终运行路径由 `SarkazV3F` 的继承链决定；Bayes、XGBoost 等词出现在来源文件中，不表示都进入保留策略。

```bash
python scripts/verify_strategy.py
```

该命令检查来源文件是否齐备以及 Python 语法。账户分析直接使用仓库附带的逐笔账本。完整信号回测需要原 Freqtrade 研究环境、5m 行情和对应配置，详见 [数据卡](../data/DATA_CARD.md)。

[当前规格与机制](../docs/STRATEGY.md) · [研究档案](../research/README.md)
