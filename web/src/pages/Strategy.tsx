import { ArrowRight, ExternalLink } from "lucide-react";
import { Panel, Tag, Metric } from "../components/ui";
import { number, percent, reasonName } from "../finance";
import { REPO } from "../config";
import type { Period } from "../types";
export default function Strategy({
  period: p,
  go,
}: {
  period: Period;
  go: (page: string) => void;
}) {
  const steps = [
    [
      "01",
      "状态过滤",
      "识别趋势、参与度与价格结构，筛选允许做多的市场状态。",
      "REGIME FILTER",
    ],
    [
      "02",
      "动量触发",
      "Signal K：大实体、异常振幅和极端成交活跃度共同定义突破。",
      "SIGNAL K",
    ],
    [
      "03",
      "收盘确认",
      "下一根已完成 K 线确认动量延续，在随后可用成交时点进入。",
      "NEXT-CLOSE CONFIRM",
    ],
    [
      "04",
      "风险配置",
      "有限权重表表达结构差异，V3F 将杠杆预算统一放大 1.50 倍。",
      "RISK EXPRESSION",
    ],
    [
      "05",
      "浮盈加仓",
      "完成 K 线收盘达到 +1R 后允许一次加仓，保留原入场盈亏平衡基准。",
      "PYRAMID AT +1R",
    ],
    [
      "06",
      "跟踪退出",
      "初始 Signal K 低点止损、原价保本、前 4 小时低点跟踪，最长持仓 24 小时。",
      "EXIT DISCIPLINE",
    ],
  ];
  return (
    <>
      <div className="strategy-banner">
        <div>
          <Tag kind="positive">FROZEN STRATEGY</Tag>
          <h2>
            让信号选择方向，
            <br />
            让风险规则决定暴露。
          </h2>
          <p>
            围绕同一个日内动量假设，分别研究入场质量、仓位表达、加仓时机与退出路径。
          </p>
        </div>
        <div className="signal-visual" aria-label="策略事件顺序示意">
          <svg viewBox="0 0 440 150">
            <path
              d="M10 119 40 109 65 113 95 89 118 96 149 70 180 65 208 72 234 48 265 56 291 33 329 38 361 18 385 26 426 12"
              fill="none"
              stroke="#80d6ba"
              strokeWidth="2"
            />
            <path
              d="M10 134h420M151 10v125M292 10v125"
              stroke="#3c494b"
              strokeDasharray="3 4"
            />
            <circle cx="149" cy="70" r="5" fill="#80d6ba" />
            <circle cx="291" cy="33" r="5" fill="#ceb78a" />
            <text x="124" y="147">
              ENTRY
            </text>
            <text x="268" y="147">
              +1R ADD
            </text>
          </svg>
          <span>规则示意 · 非行情曲线</span>
        </div>
      </div>
      <Panel
        title="策略决策链"
        subtitle="六个阶段，一个固定研究对象"
        action={
          <a
            className="text-link"
            href={REPO + "/blob/main/docs/STRATEGY.md"}
            target="_blank"
            rel="noreferrer"
          >
            策略说明 <ExternalLink size={13} />
          </a>
        }
      >
        <div className="strategy-steps">
          {steps.map(([n, title, body, en]) => (
            <div key={n} className="strategy-step">
              <div>
                <span>{n}</span>
                <ArrowRight size={16} />
              </div>
              <h3>{title}</h3>
              <small>{en}</small>
              <p>{body}</p>
            </div>
          ))}
        </div>
      </Panel>
      <div className="two-columns">
        <Panel title="收益结构" subtitle="交易统计 · 不等同于日收益统计">
          <div className="mini-metrics">
            <Metric
              label="平均盈利交易"
              value={number(p.risk.average_winner)}
              detail="USDT / TRADE"
              tone="green"
            />
            <Metric
              label="平均亏损交易"
              value={number(p.risk.average_loser)}
              detail="USDT / TRADE"
              tone="rose"
            />
            <Metric
              label="中位持仓时长"
              value={number(p.risk.median_hold_hours, 1) + "h"}
              detail="OPEN TO CLOSE"
            />
          </div>
          <div className="win-loss-bar">
            <div
              style={{ width: `${(p.base.metrics.win_rate || 0) * 100}%` }}
            />
            <div />
          </div>
          <div className="panel-bottom">
            <span>盈利交易 {percent(p.base.metrics.win_rate)}</span>
            <span>
              加仓交易 {p.base.metrics.trades_with_add} /{" "}
              {p.base.metrics.trade_count}
            </span>
          </div>
        </Panel>
        <Panel title="退出原因贡献" subtitle="原生账本归因 · P&L / USDT">
          <div className="attribution-list">
            {p.attribution.map((a) => (
              <div key={a.reason}>
                <span>
                  {reasonName(a.reason)}
                  <small>
                    {a.count} 笔 · 胜率 {percent(a.win_rate, 1)}
                  </small>
                </span>
                <strong className={a.pnl >= 0 ? "green" : "rose"}>
                  {number(a.pnl)}
                </strong>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel title="研究时间线" subtitle="明确开发区间，保留每一阶段的研究语境">
        <div className="research-timeline">
          <div>
            <span>2020 — 2023</span>
            <h3>历史前缀复核</h3>
            <p>冻结版本向历史延伸，510 笔交易与连续回测前缀逐笔一致。</p>
          </div>
          <div>
            <span>2024 — 2026.06</span>
            <h3>策略开发区间</h3>
            <p>2024 年以后包含参数与结构开发样本，全历史曲线按研究回测呈现。</p>
          </div>
          <div>
            <span>2026.10.03</span>
            <h3>连续账户扩展</h3>
            <p>固定 Sarkaz V3F，延长至最新归档时点；跨年保留账户与仓位约束。</p>
          </div>
        </div>
        <div className="panel-bottom">
          <span>收益归因基于归档结果，不将相关分组差异解释为因果消融。</span>
          <button className="text-link" onClick={() => go("trades")}>
            检查原生交易 <ArrowRight size={13} />
          </button>
        </div>
      </Panel>
    </>
  );
}
