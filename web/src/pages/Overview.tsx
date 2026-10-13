import { useMemo, useState } from "react";
import { ArrowRight, GitBranch } from "lucide-react";
import { Panel, Tag, Metric } from "../components/ui";
import { Chart, colors, lineOption } from "../Chart";
import { date, number, percent } from "../finance";
import type { Period } from "../types";
export default function Overview({
  period: p,
  periodKey,
  onMonth,
  go,
}: {
  period: Period;
  periodKey: string;
  onMonth: (month: string) => void;
  go: (page: string) => void;
}) {
  const [view, setView] = useState("equity"),
    [log, setLog] = useState(false);
  const m = p.base.metrics,
    comparison = view === "benchmark";
  const option = useMemo(
    () =>
      comparison
        ? lineOption(
            p.benchmark.map((r) => r.date),
            [
              {
                name: "RCM-3F",
                data: p.benchmark.map((r) => r.strategy),
                color: colors.green,
                area: true,
              },
              {
                name: "BTC 买入持有",
                data: p.benchmark.map((r) => r.benchmark),
                color: colors.blue,
              },
            ],
            false,
            log,
          )
        : lineOption(
            p.base.curve.map((r) => r.date),
            [
              {
                name: "策略权益 · USDT",
                data: p.base.curve.map((r) => r.equity),
                color: colors.green,
                area: true,
                step: true,
              },
            ],
            false,
            log,
          ),
    [p, comparison, log],
  );
  const dd = useMemo(
    () =>
      lineOption(
        p.base.curve.map((r) => r.date),
        [
          {
            name: "已实现回撤",
            data: p.base.curve.map((r) => -r.drawdown),
            color: colors.red,
            area: true,
            step: true,
          },
        ],
        true,
      ),
    [p],
  );
  const annual = useMemo(
    () => ({
      ...lineOption(
        p.base.yearly.map((y) => String(y.year)),
        [],
        true,
      ),
      grid: { left: 48, right: 20, top: 22, bottom: 30 },
      xAxis: {
        type: "category",
        data: p.base.yearly.map((y) => String(y.year)),
        axisLabel: { color: colors.text },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series: [
        {
          type: "bar",
          barWidth: "40%",
          data: p.base.yearly.map((y) => ({
            value: y.return,
            itemStyle: {
              color: y.year === 2026 ? colors.amber : "#6f9680",
              borderRadius: [2, 2, 0, 0],
            },
          })),
          label: {
            show: true,
            position: "top",
            fontSize: 10,
            color: "#718267",
            formatter: (a: { value: number }) => percent(a.value, 1),
          },
        },
      ],
    }),
    [p],
  );
  const years = [...new Set(p.monthly.map((r) => r.month.slice(0, 4)))];
  return (
    <>
      <div className="metrics-grid">
        <Metric
          label="累计收益 / TOTAL RETURN"
          value={"+" + percent(m.total_return)}
          detail={`期末权益 ${number(m.final_equity)} USDT`}
          tone="green"
        />
        <Metric
          label="复合年化 / CAGR"
          value={percent(m.cagr)}
          detail={
            periodKey === "all"
              ? "按原生有效区间 · 365 日年化"
              : "按所选账户区间 · 365 日年化"
          }
        />
        <Metric
          label="风险调整收益 / SHARPE"
          value={number(m.daily_sharpe, 3)}
          detail="UTC 每日账户收益 · 无风险利率 0"
        />
        <Metric
          label="最大回撤 / MAX DRAWDOWN"
          value={"−" + percent(m.max_drawdown)}
          detail="基于已实现权益 · 包含区间期初权益"
          tone="rose"
        />
      </div>
      <div className="overview-grid">
        <Panel
          title={comparison ? "策略与市场基准" : "账户权益"}
          subtitle={
            comparison
              ? "共同完整日窗口 · 起点 = 100 · 各自净值路径"
              : "连续账户 · 跨年度不重置 · USDT"
          }
          action={
            <div className="chart-actions">
              <div className="segmented">
                <button
                  className={!comparison ? "selected" : ""}
                  onClick={() => setView("equity")}
                >
                  权益
                </button>
                <button
                  className={comparison ? "selected" : ""}
                  onClick={() => setView("benchmark")}
                >
                  基准对照
                </button>
              </div>
              <button
                className={`micro-button ${log ? "on" : ""}`}
                onClick={() => setLog(!log)}
                aria-pressed={log}
              >
                LOG
              </button>
            </div>
          }
        >
          <div className="chart-legend">
            <span>
              <i style={{ background: colors.green }} />
              RCM-3F
            </span>
            {comparison && (
              <span>
                <i style={{ background: colors.blue }} />
                BTC 买入持有
              </span>
            )}
            <span className="legend-right">
              {comparison
                ? "净值指数"
                : `起始 ${number(m.opening_equity, 0)} USDT`}
            </span>
          </div>
          <Chart
            option={option}
            height={285}
            label={
              comparison ? "策略与 BTC 买入持有基准对照" : "策略账户权益曲线"
            }
          />
          <div className="subchart-label">
            UNDERWATER <span>已实现回撤</span>
            <strong className="rose">−{percent(m.max_drawdown)}</strong>
          </div>
          <Chart option={dd} height={110} label="已实现回撤曲线" />
          {comparison && (
            <p className="chart-footnote">
              BTC 为无杠杆价格参照，按首个完整日开盘买入；进出各 5
              bps。最后完整日为 {date(p.benchmark.at(-1)!.date)}
              ，与策略权益统计终点不同。
            </p>
          )}
        </Panel>
        <div className="overview-rail">
          <Panel
            title="策略画像"
            subtitle="MOMENTUM / LONG ONLY"
            action={<span className="panel-index">01</span>}
          >
            <div className="strategy-name">
              <span className="strategy-symbol">
                <GitBranch size={25} />
              </span>
              <div>
                RCM-3F<small>结构突破与动量延续</small>
              </div>
            </div>
            <dl className="key-values">
              <div>
                <dt>信号周期</dt>
                <dd>5 MIN</dd>
              </div>
              <div>
                <dt>历史交易</dt>
                <dd>
                  {m.trade_count}
                  <small>笔</small>
                </dd>
              </div>
              <div>
                <dt>盈利因子</dt>
                <dd>{number(m.profit_factor, 3)}</dd>
              </div>
              <div>
                <dt>交易胜率</dt>
                <dd>{percent(m.win_rate)}</dd>
              </div>
              <div>
                <dt>平均盈亏比</dt>
                <dd>
                  {number(p.risk.payoff)}
                  <small>×</small>
                </dd>
              </div>
            </dl>
            <button className="text-link" onClick={() => go("strategy")}>
              查看策略逻辑 <ArrowRight size={14} />
            </button>
          </Panel>
          <div className="research-note">
            <div className="note-label">
              <span />
              RESEARCH NOTE
            </div>
            <h3>
              {periodKey === "2026"
                ? "收益停滞，需要拆解。"
                : "收益来自少数趋势交易。"}
            </h3>
            <p>
              {periodKey === "2026"
                ? `当前区间收益 ${percent(m.total_return)}，盈利因子 ${number(m.profit_factor, 3)}。观察成本与退出分布，定位收益变化。`
                : `胜率 ${percent(m.win_rate)}，平均盈亏比 ${number(p.risk.payoff)} 倍。前 10 笔盈利交易占净利润 ${percent(p.risk.top10_pnl_share, 1)}。`}
            </p>
            <button className="text-link" onClick={() => go("risk")}>
              检查风险暴露 <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </div>
      <div className="bottom-grid">
        <Panel
          title="月度收益"
          subtitle="UTC 月末权益复合收益 · 点击月份检查交易"
          action={<Tag>MONTHLY RETURNS</Tag>}
        >
          <div className="heatmap-wrap">
            <table className="heatmap">
              <thead>
                <tr>
                  <th>YEAR</th>
                  {Array.from({ length: 12 }, (_, i) => (
                    <th key={i}>{String(i + 1).padStart(2, "0")}</th>
                  ))}
                  <th>YTD</th>
                </tr>
              </thead>
              <tbody>
                {years.map((year) => (
                  <tr key={year}>
                    <th>{year}</th>
                    {Array.from({ length: 12 }, (_, i) => {
                      const month = `${year}-${String(i + 1).padStart(2, "0")}`,
                        r = p.monthly.find((m) => m.month === month);
                      return (
                        <td key={i}>
                          {r ? (
                            <button
                              onClick={() => onMonth(month)}
                              title={`${month}：${r.trades} 笔交易，${number(r.pnl)} USDT`}
                              aria-label={`${month} 收益 ${percent(r.return)}，查看交易`}
                              style={{
                                background:
                                  r.return >= 0
                                    ? `rgba(98,181,151,${0.08 + Math.min(Math.abs(r.return), 0.6) * 0.65})`
                                    : `rgba(217,125,124,${0.1 + Math.min(Math.abs(r.return), 0.4) * 0.8})`,
                                color: r.return >= 0 ? "#386b4b" : "#975545",
                              }}
                            >
                              {(r.return * 100).toFixed(1)}
                            </button>
                          ) : (
                            <span className="missing-cell">—</span>
                          )}
                        </td>
                      );
                    })}
                    <td className="year-return">
                      {percent(
                        p.base.yearly.find((y) => String(y.year) === year)!
                          .return,
                        1,
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="panel-bottom">
            <span>
              单位：% ·{" "}
              {periodKey === "all" || periodKey === "2026"
                ? "2026 年截至 10 月 3 日"
                : "期末按 UTC 边界"}
            </span>
            <span className="heat-legend">
              <i />
              负收益 <i />
              正收益
            </span>
          </div>
        </Panel>
        <Panel title="年度收益" subtitle="连续账户收益率">
          <Chart option={annual} height={245} label="年度收益柱状图" />
        </Panel>
      </div>
    </>
  );
}
