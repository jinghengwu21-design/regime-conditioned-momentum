# 数据与开源组件

本目录新增的软件代码使用 MIT License。依赖通过包管理器安装，其许可分别适用；`requirements.lock` 给出当前测试版本。

| 组件 | 用途 | 上游许可 |
|---|---|---|
| React | 研究终端界面 | MIT |
| Apache ECharts | SVG 金融图表 | Apache-2.0 |
| Lucide | 界面图标 | ISC |
| Vite / TypeScript | 前端构建 / 类型检查 | MIT / Apache-2.0 |
| Inter / IBM Plex Mono | 本地字体 | SIL Open Font License 1.1 |
| LangGraph | 状态与条件流程 | MIT |
| OpenAI Python SDK | 模型函数工具接口 | Apache-2.0 |
| pandas / NumPy | 数据与数值计算 | BSD-3-Clause |
| Plotly.py / Plotly.js | 交互图表，HTML 报告内含 Plotly.js | MIT |
| Pydantic | 参数与报告 schema | MIT |
| HTTPX | SDK 契约测试传输 | BSD-3-Clause |
| PyArrow | 既有 feather 行情读取 | Apache-2.0 |
| pytest | 软件验收 | MIT |

字体许可原文见 `docs/licenses/`。前端版本锁定于 `web/package-lock.json`。

原项目使用 Freqtrade（GPL-3.0）作为交易与回测引擎；本包接入其用户生成的回测结果，没有复制其引擎源代码。作者的策略研究源码保存在 `strategy/frozen/`，以 `strategy/manifest.json` 校验；运行这些策略需要另行安装 Freqtrade 并遵守其许可。

行情样例来自原项目保存的 OKX 公开市场数据，权利遵循原提供方条款；软件 MIT 许可不改变行情数据的权利归属。回测账本是原研究项目的模拟结果，样例导出仅保留研究所需字段。来源及变换过程见 `data/manifest.json` 和 `scripts/build_dataset.py`。
