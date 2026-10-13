import { useMemo } from "react";
import { ArrowUpRight, ArrowRight } from "lucide-react";
import { Chart, colors, lineOption } from "../Chart";
import { number, percent } from "../finance";
import type { Period } from "../types";
import type { Chronicle } from "../research";
import { statusLabel } from "../research";

export default function Research({
  data,
  period: p,
  go,
}: {
  data: Chronicle;
  period: Period;
  go: (id: string) => void;
}) {
  const chart = useMemo(
    () =>
      lineOption(
        p.base.curve.map((v) => v.date),
        [
          {
            name: "RCM-3F · USDT",
            data: p.base.curve.map((v) => v.equity),
            color: colors.green,
            area: true,
            step: true,
          },
        ],
      ),
    [p],
  );
  const stages = [
    {
      n: "01",
      date: "02—16 JUN",
      title: "重建可执行基线",
      body: "RLRS、M / K / N 系列与 PA5M：从成交审计、单仓竞争到跨年代检验。",
      id: "R01",
      count: "R01—R06",
    },
    {
      n: "02",
      date: "17—29 JUN",
      title: "形成条件动量规则",
      body: "Signal K、异常参与、结构状态、有限权重与原入场价保本。",
      id: "R07",
      count: "R07—R18",
    },
    {
      n: "03",
      date: "LATE JUN—JUL",
      title: "扩展与反证",
      body: "多空组合、机器学习状态、因子替代与独立策略家族，逐条保留或淘汰。",
      id: "R23",
      count: "R19—R45",
    },
    {
      n: "04",
      date: "JUL—OCT",
      title: "执行复盘与历史延伸",
      body: "排查漏单、加仓路径与容器一致性，再把固定规则延伸到连续账户。",
      id: "R46",
      count: "R46—R48",
    },
  ];
  return (
    <>
      <section className="research-hero">
        <div className="hero-copy">
          <div className="eyebrow">RESEARCH MONOGRAPH / 01</div>
          <h1>
            Regime-conditioned
            <br />
            <em>momentum.</em>
          </h1>
          <h2>市场状态条件动量研究</h2>
          <p className="hero-lead">
            研究一个持续的问题：异常上涨何时具有后续延续性，以及如何把它转化为可执行的风险暴露。
          </p>
          <div className="hero-methods">
            <span>结构状态</span>
            <span>异常成交量</span>
            <span>有限风险权重</span>
          </div>
          <div className="hero-actions">
            <button className="button primary" onClick={() => go("strategy")}>
              阅读保留策略 <ArrowUpRight size={16} />
            </button>
            <button className="text-link" onClick={() => go("archive")}>
              完整研究档案 <ArrowRight size={15} />
            </button>
          </div>
          <div className="author-line">
            <span>吴静恒</span>
            <span>Independent systematic research</span>
          </div>
        </div>
        <div className="hero-ledger">
          <div className="ledger-title">
            <span>RCM-3F / CONTINUOUS ACCOUNT</span>
            <span>BTC · 5m</span>
          </div>
          <div className="ledger-value">
            {number(p.base.metrics.final_equity)}
            <small>USDT</small>
          </div>
          <div className="ledger-sub">
            1,000 USDT 初始权益 · 2020.01—2026.10
          </div>
          <Chart option={chart} height={233} label="RCM-3F 连续历史账户权益" />
          <div className="ledger-metrics">
            <div>
              <span>CAGR</span>
              <strong>{percent(p.base.metrics.cagr)}</strong>
            </div>
            <div>
              <span>最大已实现回撤</span>
              <strong>{percent(p.base.metrics.max_drawdown)}</strong>
            </div>
            <div>
              <span>交易数</span>
              <strong>{p.base.metrics.trade_count}</strong>
            </div>
          </div>
          <div className="ledger-foot">
            <span>回测 · 单边 5 bps · 资金费未计</span>
            <button onClick={() => go("performance")}>
              查看账户分析 <ArrowUpRight size={13} />
            </button>
          </div>
        </div>
      </section>
      <div className="research-strip">
        <span>研究范围</span>
        <strong>BTC 永续 / 5 分钟 / 单向做多</strong>
        <span>研究档案</span>
        <strong>{data.cases.length} 个决策节点</strong>
        <span>当前版本</span>
        <strong>RCM-3F</strong>
      </div>
      <section className="editorial-section">
        <div className="section-intro">
          <div className="eyebrow">THE RESEARCH PATH</div>
          <h2>策略是怎样留下来的</h2>
          <p>从失败中提炼方法，再决定下一轮值得研究什么。</p>
        </div>
        <div className="phase-grid">
          {stages.map((s) => (
            <button
              className="phase"
              key={s.n}
              onClick={() => go("archive/" + s.id)}
            >
              <div className="phase-top">
                <span>{s.n}</span>
                <small>{s.date}</small>
              </div>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
              <div className="phase-end">
                {s.count}
                <ArrowUpRight size={16} />
              </div>
            </button>
          ))}
        </div>
      </section>
      <section className="editorial-section research-reading">
        <div className="section-intro">
          <div className="eyebrow">SELECTED FINDINGS</div>
          <h2>关键研究笔记</h2>
          <p>筛选、权重与交易管理分别回答不同的问题。</p>
          <button className="text-link" onClick={() => go("archive")}>
            浏览全部 {data.cases.length} 个节点 <ArrowRight size={15} />
          </button>
        </div>
        <div className="finding-list">
          {["R08", "R14", "R23", "R41"].map((id) => {
            const c = data.cases.find((c) => c.id === id)!;
            return (
              <button key={id} onClick={() => go("archive/" + id)}>
                <span className="finding-number">{id}</span>
                <div>
                  <div className="finding-kicker">
                    {c.methodLabel}
                    <span className={`status-label ${c.status}`}>
                      {statusLabel[c.status]}
                    </span>
                  </div>
                  <h3>{c.title}</h3>
                  <p>{c.lesson}</p>
                </div>
                <ArrowUpRight size={19} />
              </button>
            );
          })}
        </div>
      </section>
      <section className="research-close">
        <div>
          <div className="eyebrow">RESEARCH OPERATIONS</div>
          <h2>把研究讨论变成可复用的实验记忆。</h2>
          <p>
            假设、固定规格、实现、回测、复核、裁决；一次失败也为下一轮限定问题。
          </p>
        </div>
        <button className="button" onClick={() => go("process")}>
          Agent 研究循环 <ArrowRight size={16} />
        </button>
      </section>
    </>
  );
}
