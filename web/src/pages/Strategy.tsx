import { useState } from "react";
import { ArrowUpRight, ArrowRight, ChevronDown } from "lucide-react";
import { REPO } from "../config";
import type { Period } from "../types";
import { percent, number } from "../finance";

const mechanisms = [
  {
    id: "R10",
    n: "01",
    name: "异常参与的价格冲击",
    code: "SIGNAL K + VOLUME",
    rule: "阳线实体占振幅 ≥ 0.70，振幅处于过去三日 q90 以上，成交量 z-score > 4。",
    mechanism:
      "长实体描述方向性冲击，异常量描述参与规模。二者共同区分普通上涨与集中交易事件。",
    evidence:
      "成交量把 7,321 个形态事件收窄至 857 个。TFI 正值却保留 99.65% 的可用条件事件，方向重复，未能替代异常量。",
    level: "事件筛选与替代检验",
    caveat: "事件数来自 2020–2023 因子库；单小时均值不能代表完整策略收益。",
  },
  {
    id: "R26",
    n: "02",
    name: "市场状态与拍卖位置",
    code: "REGIME + STRUCTURE",
    rule: "Regime V2 使用已知 session、24h VWAP 与价值接受关系；结构为 2h 高点突破，或 24h VWAP 支撑回测后的 1h 高点收复。",
    mechanism:
      "相同上涨冲击，在上方接受与下方拒绝两种背景中，后续供求过程不同。状态描述冲击发生的位置。",
    evidence:
      "完整删除入场 context 后，499 → 566 笔；收益增加，但 PF 1.412 → 1.290，回撤 30.02% → 32.83%，仅 3 个半年度改善。",
    level: "原生删除对照",
    caveat: "这是对整组 context 的检验，不能分配为每一个状态子条件的独立贡献。",
  },
  {
    id: "R12",
    n: "03",
    name: "观察接受，再分配暴露",
    code: "NEXT CLOSE + FINITE WEIGHTS",
    rule: "信号延迟一根已完成 K 线进入。下一收盘的强弱、风险标签与 Fresh > 24h 共同决定有限权重；弱确认仍可交易。",
    mechanism:
      "观察一个额外收盘能读取冲击后的接受情况，但也付出价格变化与延迟成本。保留机会，通过权重表达差异。",
    evidence:
      "历史概念归因中，clean low-confirm 160 笔、PF 1.949；risk low-confirm 113 笔、PF 0.595。简单删除所有弱确认会同时失去前者。",
    level: "分组归因与研究取舍",
    caveat: "归因窗口为 2020.07–2023.12，共 451 笔；分组差异是描述证据。",
  },
  {
    id: "R14",
    n: "04",
    name: "趋势展开后的单次加仓",
    code: "+1R PYRAMID / ORIGINAL BE",
    rule: "已完成 K 线收盘达到 +1R 后加仓一次，约原始名义仓位的 25%；保本继续锚定原入场价。",
    mechanism:
      "在价格已朝预期方向展开后增加暴露，避免加仓抬高均价后过早触发保本退出，给趋势留下空间。",
    evidence:
      "WG 与加仓／原价保本组合对照：同为 365 笔，收益 141.31% → 169.20%。161 笔加仓交易贡献 +457.14 USDT，204 笔未加仓交易贡献 −178.27 USDT 的账户差额。",
    level: "成组规则对照",
    caveat:
      "对照同时涉及预留、加仓与保本；包含复利影响，不能归为保本单因素效应。",
  },
  {
    id: "R16",
    n: "05",
    name: "固定信号，统一风险预算",
    code: "RCM-3 → RCM-3F",
    rule: "RCM-3F 保留交易逻辑，把最终杠杆乘以 1.50。开发期约 20% 回撤预算确定后，再检查历史段。",
    mechanism: "风险放大提升账户对同一机会序列的暴露；不会创造新的信号优势。",
    evidence:
      "历史 510 笔保持相同：CAGR 31.00% → 46.44%，回撤 20.95% → 30.09%，PF 1.450 → 1.413。",
    level: "相同交易序列对照",
    caveat: "历史区间并未维持开发期约 20% 的回撤水平。",
  },
  {
    id: "R15",
    n: "06",
    name: "让收益保留右尾",
    code: "STRUCTURAL TRAIL / 24H",
    rule: "Signal K 低点为初始风险锚；原入场价保本、前 4h 低点跟踪，最长持仓 24h；同一拍卖段抑制重复信号。",
    mechanism:
      "低胜率策略依赖少数大趋势，过早退出可能改善局部回撤，同时截断重要的盈利尾部。",
    evidence:
      "POC 条件跟踪与其他提前退出未替代基线。HighAdd50 和第二次信号加仓也因历史风险代价被撤回。",
    level: "退出与加仓候选比较",
    caveat: "右尾依赖意味着漏掉少量趋势交易就可能显著改变账户结果。",
  },
];

export default function Strategy({
  period: p,
  go,
}: {
  period: Period;
  go: (page: string) => void;
}) {
  const [window, setWindow] = useState("history");
  const history = window === "history";
  const comparison = history
    ? [
        ["交易数", "510", "510", "机会序列相同"],
        ["累计收益", "+193.81%", "+358.45%", "提高风险暴露"],
        ["CAGR", "31.00%", "46.44%", "+15.44 pp"],
        ["最大回撤", "20.95%", "30.09%", "+9.14 pp"],
        ["盈利因子", "1.450", "1.413", "账户复利与仓位路径"],
      ]
    : [
        ["交易数", "365", "365", "机会序列相同"],
        ["累计收益", "+169.20%", "+317.66%", "提高风险暴露"],
        ["CAGR", "49.29%", "78.33%", "+29.04 pp"],
        ["最大回撤", "13.29%", "19.38%", "+6.09 pp"],
        ["盈利因子", "1.627", "1.557", "账户复利与仓位路径"],
      ];
  return (
    <>
      <section className="strategy-abstract">
        <div>
          <div className="eyebrow">RETAINED SPECIFICATION / RCM-3F</div>
          <h2>
            异常参与下的结构突破，
            <br />
            以状态和接受情况分配风险。
          </h2>
          <p>
            保留规则经历了入场替代、状态删除、权重比较、加仓与退出实验。名称对应三项实际方法：条件状态、事件动量、有限风险配置。
          </p>
        </div>
        <dl>
          <div>
            <dt>市场</dt>
            <dd>BTC / USDT 永续</dd>
          </div>
          <div>
            <dt>信号 / 执行</dt>
            <dd>5m / Freqtrade 原生</dd>
          </div>
          <div>
            <dt>方向 / 容量</dt>
            <dd>单向做多 / 单仓</dd>
          </div>
          <div>
            <dt>单笔管理</dt>
            <dd>一次 +1R 加仓 / 最长 24h</dd>
          </div>
        </dl>
      </section>
      <section className="editorial-section">
        <div className="section-heading">
          <div>
            <div className="eyebrow">MECHANISM & EVIDENCE</div>
            <h2>规则背后的解释与检验</h2>
          </div>
          <a
            className="text-link"
            href={REPO + "/blob/main/docs/STRATEGY.md"}
            target="_blank"
            rel="noreferrer"
          >
            完整规格 <ArrowUpRight size={14} />
          </a>
        </div>
        <p className="section-note">
          机制解释是经济假设；对照实验检验规则改变的效果；分组归因描述结果。以下逐项给出对应的证据。
        </p>
        <div className="mechanisms">
          {mechanisms.map((m, i) => (
            <details key={m.n} open={i === 0}>
              <summary>
                <span className="mechanism-number">{m.n}</span>
                <div>
                  <h3>{m.name}</h3>
                  <small>{m.code}</small>
                </div>
                <span className="mechanism-level">{m.level}</span>
                <ChevronDown size={17} />
              </summary>
              <div className="mechanism-body">
                <div>
                  <span>实际规则</span>
                  <p>{m.rule}</p>
                  <span>机制解释</span>
                  <p>{m.mechanism}</p>
                </div>
                <div>
                  <span>检验结果</span>
                  <p>{m.evidence}</p>
                  <small>{m.caveat}</small>
                  <button
                    className="text-link"
                    onClick={() => go("archive/" + m.id)}
                  >
                    阅读研究节点 {m.id} <ArrowUpRight size={14} />
                  </button>
                </div>
              </div>
            </details>
          ))}
        </div>
      </section>
      <section className="editorial-section factor-diagnostic">
        <div className="section-intro">
          <div className="eyebrow">EVENT DIAGNOSTICS / 2020–2023</div>
          <h2>事件是怎样被收窄的</h2>
          <p>
            对同一事件池逐层应用参与度、结构与状态条件，观察覆盖，而后进入原生账户研究。
          </p>
          <button className="text-link" onClick={() => go("archive/R29")}>
            因子库与替代检验 <ArrowRight size={14} />
          </button>
        </div>
        <div>
          <div className="funnel-rows">
            {[
              ["Signal K", 7321],
              ["+ 异常成交量", 857],
              ["+ 结构选择", 755],
              ["+ Regime V2", 651],
            ].map(([label, count]) => (
              <div className="funnel-row" key={label}>
                <span>{label}</span>
                <div className="funnel-track">
                  <i style={{ width: `${(Number(count) / 7321) * 100}%` }} />
                </div>
                <strong>{Number(count).toLocaleString()}</strong>
                <small>{((Number(count) / 7321) * 100).toFixed(1)}%</small>
              </div>
            ))}
          </div>
          <p className="chart-footnote">
            这里统计条件事件，尚未应用单仓与持仓管理。完整条件的 1h 净延续均值为
            −2.00 bps；完整策略通过更长持仓、仓位和退出表达收益。
          </p>
        </div>
      </section>
      <section className="editorial-section strategy-comparison">
        <div className="section-intro">
          <div className="eyebrow">CONTROLLED COMPARISON</div>
          <h2>
            信号没有变，
            <br />
            风险预算变了。
          </h2>
          <p>
            RCM-3 与 RCM-3F 的原生比较。先在开发样本确定 1.50 倍预算，再向
            2020–2023 年延伸。
          </p>
          <button className="text-link" onClick={() => go("archive/R16")}>
            版本选择过程 <ArrowRight size={14} />
          </button>
        </div>
        <div>
          <div className="comparison-header">
            <div className="segmented">
              <button
                className={history ? "selected" : ""}
                onClick={() => setWindow("history")}
              >
                2020–2023 历史
              </button>
              <button
                className={!history ? "selected" : ""}
                onClick={() => setWindow("development")}
              >
                2024–2026.06 开发
              </button>
            </div>
            <span>单边 5 bps · 资金费未计</span>
          </div>
          <table className="comparison-table">
            <thead>
              <tr>
                <th>指标</th>
                <th>RCM-3</th>
                <th>RCM-3F</th>
                <th>解释</th>
              </tr>
            </thead>
            <tbody>
              {comparison.map((r) => (
                <tr key={r[0]}>
                  {r.map((v, i) =>
                    i === 0 ? <th key={i}>{v}</th> : <td key={i}>{v}</td>,
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="chart-footnote">
            历史段后来被多轮研究复用；这里保留当时实验次序与窗口，不作为当前未见样本。
          </p>
        </div>
      </section>
      <section className="editorial-section weight-section">
        <div className="section-heading">
          <div>
            <div className="eyebrow">EXPOSURE EXPRESSION</div>
            <h2>有限权重表</h2>
          </div>
          <span className="section-note">
            基准 WG 层 · 加仓预留和 1.50 倍预算另行应用
          </span>
        </div>
        <div className="weight-grid">
          {[
            ["弱确认 · 低风险", "0.75", "1.00"],
            ["弱确认 · 风险标签", "0.50", "1.00"],
            ["强确认 · 风险标签", "0.75", "1.25"],
            ["强确认 · 低风险", "1.00", "1.50"],
            ["新鲜强确认 · 低风险", "1.00", "1.75"],
          ].map(([label, stake, lev]) => (
            <div key={label}>
              <span>{label}</span>
              <div>
                <strong>{stake}</strong>
                <small>stake ×</small>
                <strong>{lev}</strong>
                <small>leverage ×</small>
              </div>
            </div>
          ))}
        </div>
        <p className="chart-footnote">
          风险标签涵盖周末 UTC、ClimaxBody 与压缩波动等条件。初始保证金
          ×0.80、杠杆 ×1.25 用于加仓预留；RCM-3F 再把杠杆
          ×1.50。表中数值是层级系数。
        </p>
      </section>
      <section className="research-close">
        <div>
          <div className="eyebrow">PAYOFF PROFILE / FULL HISTORY</div>
          <h2>
            胜率 {percent(p.base.metrics.win_rate)}，平均盈亏比{" "}
            {number(p.risk.payoff)} 倍。
          </h2>
          <p>
            这使成本、趋势捕获和漏单成为策略的核心运行问题。前 10 笔赢家占净利润{" "}
            {percent(p.risk.top10_pnl_share, 1)}。
          </p>
        </div>
        <button className="button" onClick={() => go("risk")}>
          检查收益结构 <ArrowRight size={16} />
        </button>
      </section>
    </>
  );
}
