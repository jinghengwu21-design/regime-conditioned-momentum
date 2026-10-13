import { useMemo, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { Panel, Metric, Tag } from "../components/ui";
import { Chart, colors, lineOption } from "../Chart";
import { date, number, percent, stress } from "../finance";
import type { Period } from "../types";
export default function Risk({ period: p }: { period: Period }) {
  const [fee, setFee] = useState(8),
    [slip, setSlip] = useState(0);
  const s = useMemo(() => stress(p, fee, slip), [p, fee, slip]);
  const chart = useMemo(
    () =>
      lineOption(
        s.curve.map((r) => r.date),
        [
          {
            name: "基准 · 5 bps",
            data: p.base.curve.map((r) => r.equity),
            color: colors.blue,
            step: true,
          },
          {
            name: `情景 · ${fee} bps + ${slip} bps 滑点`,
            data: s.curve.map((r) => r.equity),
            color: colors.amber,
            area: true,
            step: true,
          },
        ],
      ),
    [p, s, fee, slip],
  );
  const rolling = useMemo(
    () =>
      lineOption(
        p.daily.map((r) => r.date),
        [
          {
            name: "126 日滚动 Sharpe",
            data: p.daily.map((r) => r.rolling_sharpe),
            color: colors.green,
          },
        ],
      ),
    [p],
  );
  return (
    <>
      <div className="risk-top">
        <Panel
          title="成本敏感性"
          subtitle="固定成交名义金额 · 包含所有入场、加仓与退出"
          action={<SlidersHorizontal size={17} />}
        >
          <div className="sliders">
            <label>
              单边手续费
              <strong>
                {fee.toFixed(1)} <small>bps</small>
              </strong>
              <input
                type="range"
                aria-label="单边手续费"
                min="0"
                max="15"
                step="0.5"
                value={fee}
                onChange={(e) => setFee(+e.target.value)}
              />
              <span>
                0 bps <span>15 bps</span>
              </span>
            </label>
            <label>
              每次成交附加滑点
              <strong>
                {slip.toFixed(1)} <small>bps</small>
              </strong>
              <input
                type="range"
                aria-label="每次成交附加滑点"
                min="0"
                max="10"
                step="0.5"
                value={slip}
                onChange={(e) => setSlip(+e.target.value)}
              />
              <span>
                0 bps <span>10 bps</span>
              </span>
            </label>
          </div>
          <div className="scenario-presets">
            <span>情景</span>
            {[5, 8, 12].map((v) => (
              <button
                key={v}
                className={fee === v && slip === 0 ? "selected" : ""}
                onClick={() => {
                  setFee(v);
                  setSlip(0);
                }}
              >
                {v === 5 ? "基准" : v === 8 ? "适度压力" : "高成本"} · {v} bps
              </button>
            ))}
          </div>
        </Panel>
        <div className="risk-kpis">
          <Metric
            label="情景期末权益"
            value={number(s.equity)}
            detail={`基准 ${number(p.base.metrics.final_equity)} USDT`}
            tone={s.equity > 0 ? "amber" : "rose"}
          />
          <Metric
            label="增量交易成本"
            value={number(s.totalCost)}
            detail={`${number(p.base.metrics.turnover_usdt, 0)} USDT 总成交额`}
          />
          <Metric
            label="情景最大回撤"
            value={percent(s.maxDrawdown)}
            detail="平仓时确认增量成本"
            tone="rose"
          />
        </div>
      </div>
      <div className="risk-grid">
        <Panel title="权益如何被成本改变" subtitle="原持仓与成交路径保持固定">
          <div className="chart-legend">
            <span>
              <i style={{ background: colors.blue }} />
              原始账本
            </span>
            <span>
              <i style={{ background: colors.amber }} />
              当前成本情景
            </span>
          </div>
          <Chart option={chart} height={300} label="成本压力与基准权益对照" />
          <p className="chart-footnote">
            每笔增量成本 = 全部成交金额 ×（新手续费 − 5 bps +
            滑点）。费用在交易平仓时入账，未重新求解仓位和成交路径。
          </p>
        </Panel>
        <Panel title="风险观测" subtitle="基于已实现账户收益">
          <dl className="key-values risk-values">
            <div>
              <dt>最长连续亏损</dt>
              <dd>
                {p.risk.max_losing_streak} <small>笔</small>
              </dd>
            </div>
            <div>
              <dt>前 10 笔盈利 / 净利润</dt>
              <dd>{percent(p.risk.top10_pnl_share, 1)}</dd>
            </div>
            <div>
              <dt>年化日收益波动率</dt>
              <dd>{percent(p.risk.daily_volatility)}</dd>
            </div>
            <div>
              <dt>历史日收益 ES 95%</dt>
              <dd>{percent(p.risk.historical_es95)}</dd>
            </div>
            <div>
              <dt>静态盈亏平衡手续费</dt>
              <dd className="amber">
                {number(p.risk.break_even_fee_bps)} <small>bps</small>
              </dd>
            </div>
          </dl>
          <p className="chart-footnote">
            ES 为最差 5% 日收益的平均损失。前 10
            笔盈利可能超过净利润，因为其余交易包含亏损。平仓权益不包含持仓中的浮动亏损。
          </p>
        </Panel>
      </div>
      <div className="two-columns">
        <Panel title="回撤与恢复" subtitle="从前高到恢复 · 未恢复段保留截至日">
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>前高 / 谷底</th>
                  <th>回撤</th>
                  <th>持续</th>
                  <th>恢复状态</th>
                </tr>
              </thead>
              <tbody>
                {p.drawdowns.slice(0, 5).map((d) => (
                  <tr key={d.peak}>
                    <td>
                      {date(d.peak)}
                      <small>{date(d.trough)}</small>
                    </td>
                    <td className="rose mono">−{percent(d.depth)}</td>
                    <td className="mono">{Math.round(d.days)} 天</td>
                    <td>
                      {d.recovered ? (
                        <span className="muted">{date(d.recovery!)}</span>
                      ) : (
                        <Tag kind="warning">尚未恢复</Tag>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
        <Panel
          title="滚动风险调整收益"
          subtitle="126 日窗口 · 365 日年化 · 无风险利率 0"
        >
          <Chart option={rolling} height={265} label="126日滚动Sharpe" />
        </Panel>
      </div>
    </>
  );
}
