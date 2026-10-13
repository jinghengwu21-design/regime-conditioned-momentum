import { useState } from "react";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import Agent from "./Agent";
import { REPO } from "../config";
import type { Chronicle } from "../research";

const episodes = [
  {
    id: "R41",
    label: "TFI 替代异常量",
    stages: [
      "异常量会不会只是在重复上涨方向？引入主动买卖成交量差作为候选。",
      "固定同根 TFI > 0 替代 volume z > 4。提前确定样本量、分块和 bootstrap 检验。",
      "读取 Binance 47 个月官方文件，构建 411,840 根 5m 网格，先核对全市场符号分布。",
      "全市场正值占 49.30%；条件事件中 2,306 / 2,314 为正值，原异常量参考仍有更高 +1R 先达率。",
      "筛选几乎全通过说明条件冗余。八项预定检查仅通过四项，否决收益回测升级。",
      "记录失败机制与数据接口。后续研究不再把同根方向性成交确认作为独立参与度因子。",
    ],
  },
  {
    id: "R14",
    label: "加仓与原价保本",
    stages: [
      "少数趋势承担主要收益；研究何时增加暴露，以及保本锚是否过早截断趋势。",
      "固定 +1R 已完成收盘、单次约 25% 加仓、初始保证金预留与原入场价保本。",
      "把动态止损、stake 与仓位调整落实到原生回调，再对照交易编号和退出时刻。",
      "365 笔保持相同，收益 141.31% → 169.20%；加仓与非加仓路径分别贡献不同账户差额。",
      "改善来自成组管理规则与账户路径。继续测试更大加仓和第二次加仓后，历史风险代价上升。",
      "保留一次加仓与原价保本；关闭 HighAdd50 和二次信号加仓，避免继续增加自由度。",
    ],
  },
  {
    id: "R23",
    label: "状态教师与 XGBoost",
    stages: [
      "规则 Regime 的离散边界是否可以由数据驱动状态模型替代？",
      "先用规则标签训练 XGBoost，检查分类一致率；再单独评估策略过滤效果。",
      "实现训练、时点对齐、状态概率导出与在线/离线推断接口。",
      "分类 accuracy 约 94.63%，macro-F1 约 94.86%；替换策略过滤后，交易数和收益下降。",
      "复刻规则的分类指标不等于交易优势。研究转向 GMM 潜在标签与滚动推断。",
      "保留状态建模工程和 PIT 接口，RCM-3F 继续使用已检验的规则状态。",
    ],
  },
  {
    id: "R26",
    label: "删除市场状态",
    stages: [
      "状态过滤缩减机会；直接删除整组 context 是否能获得更好的长期结果？",
      "固定入场事件、单仓与交易管理，只删除入场 context，在共同训练期原生比较。",
      "完成等价代码检查与逐笔回放，记录新增交易、资金占用及半年分块。",
      "499 → 566 笔；收益 341.71% → 364.65%，PF 1.412 → 1.290，回撤 30.02% → 32.83%。",
      "仅 3 个半年度改善，额外机会降低了交易质量。继续研究状态替代，而非仅以总收益选版。",
      "保留 Regime V2。后续路径效率、Jump Model 等候选沿用覆盖与分块标准。",
    ],
  },
];
const stages = [
  "提出问题",
  "固定实验规格",
  "实现与数据核对",
  "回测与对照",
  "复核与讨论",
  "裁决与研究记忆",
];

export default function Process({
  data,
  go,
  api,
}: {
  data: Chronicle;
  go: (id: string) => void;
  api: { model_configured: boolean } | null;
}) {
  const [tab, setTab] = useState("research");
  const [episode, setEpisode] = useState("R41");
  const [step, setStep] = useState(0);
  const e = episodes.find((e) => e.id === episode)!;
  const c = data.cases.find((c) => c.id === e.id)!;
  return (
    <>
      <div className="process-tabs segmented">
        <button
          className={tab === "research" ? "selected" : ""}
          onClick={() => setTab("research")}
        >
          策略研究循环
        </button>
        <button
          className={tab === "runtime" ? "selected" : ""}
          onClick={() => setTab("runtime")}
        >
          分析 Agent · 可运行实验
        </button>
      </div>
      {tab === "runtime" ? (
        <Agent api={api} />
      ) : (
        <>
          <section className="process-intro">
            <div>
              <div className="eyebrow">HUMAN-DIRECTED / AGENT-EXECUTED</div>
              <h2>
                研究者决定问题，
                <br />
                Agent 把假设推进到可裁决的实验。
              </h2>
            </div>
            <p>
              历史研究中的 Agent
              承担资料检索、候选实现、批量回测、逐笔比较与文档归档。研究者持续质疑收益来源、样本量与过拟合，并决定研究方向和去留。
            </p>
          </section>
          <section className="cycle-workbench">
            <div className="episode-tabs">
              {episodes.map((v) => (
                <button
                  key={v.id}
                  className={episode === v.id ? "selected" : ""}
                  onClick={() => {
                    setEpisode(v.id);
                    setStep(0);
                  }}
                >
                  {v.label}
                  <small>{v.id}</small>
                </button>
              ))}
            </div>
            <div className="cycle-content">
              <nav aria-label="研究循环阶段">
                {stages.map((s, i) => (
                  <button
                    key={s}
                    className={step === i ? "active" : ""}
                    onClick={() => setStep(i)}
                  >
                    <span>{String(i + 1).padStart(2, "0")}</span>
                    {s}
                    <ArrowRight size={14} />
                  </button>
                ))}
              </nav>
              <article>
                <div className="eyebrow">
                  {e.id} / STEP {step + 1} OF 6
                </div>
                <h3>{stages[step]}</h3>
                <p>{e.stages[step]}</p>
                <div className="cycle-artifact">
                  <span>本轮裁决</span>
                  <strong>{c.decision}</strong>
                </div>
                <div className="cycle-bottom">
                  <button
                    className="text-link"
                    onClick={() => go("archive/" + e.id)}
                  >
                    打开研究记录 <ArrowUpRight size={14} />
                  </button>
                  <button
                    className="button"
                    onClick={() => setStep((step + 1) % stages.length)}
                  >
                    {step === 5 ? "回到研究问题" : "下一阶段"}
                    <ArrowRight size={14} />
                  </button>
                </div>
              </article>
            </div>
          </section>
          <section className="editorial-section research-reading">
            <div className="section-intro">
              <div className="eyebrow">WHAT CHANGED IN THE PROCESS</div>
              <h2>循环中的方法进化</h2>
              <p>经验被保存在下一次实验的设计里。</p>
            </div>
            <div className="process-lessons">
              <article>
                <span>01 / EXECUTION</span>
                <h3>从事件收益走向原生账户</h3>
                <p>
                  把可成交时点、单仓阻挡、保证金占用和加仓回调加入研究。事件层通过后，再观察真实调度如何改变结果。
                </p>
              </article>
              <article>
                <span>02 / RESEARCH DESIGN</span>
                <h3>从追加阈值走向有限候选</h3>
                <p>
                  固定基线和候选规格，用覆盖率、时间块、成本、增量与集中度决定是否升级。失败后保留关闭理由，减少重复探索。
                </p>
              </article>
              <article>
                <span>03 / STATE MODELING</span>
                <h3>从分类准确率走向交易增量</h3>
                <p>
                  规则教师、GMM 潜在状态与 XGBoost
                  推断分别回答不同问题。只有在交易质量和风险表达上成立的变化，才进入策略。
                </p>
              </article>
              <article>
                <span>04 / CONTEXT</span>
                <h3>从聊天结论走向研究账本</h3>
                <p>
                  问题、假设、实验、裁决和源报告相互关联。因子库的 34
                  个定义中，5 个活动、8 个诊断、20 个拒绝、1 个提议；状态来自 10
                  月 3 日快照。
                </p>
              </article>
            </div>
          </section>
          <section className="research-close">
            <div>
              <div className="eyebrow">EXECUTABLE ANALYSIS</div>
              <h2>把结论生成与数值复核放进可运行流程。</h2>
              <p>
                本仓库的 LangGraph 分析 Agent
                提供六个研究工具、结构化报告和五类录制实验，可在本地重新执行。
              </p>
            </div>
            <button className="button" onClick={() => setTab("runtime")}>
              打开运行实验 <ArrowRight size={16} />
            </button>
          </section>
          <a
            className="text-link document-link"
            href={REPO + "/blob/main/docs/AGENT_RESEARCH.md"}
            target="_blank"
            rel="noreferrer"
          >
            Agent 研究方法与实现 <ArrowUpRight size={14} />
          </a>
        </>
      )}
    </>
  );
}
