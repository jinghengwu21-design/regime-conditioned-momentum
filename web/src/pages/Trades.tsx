import { useMemo, useState, useEffect } from "react";
import {
  ArrowDownToLine,
  Search,
  ChevronLeft,
  ChevronRight,
  ArrowUpRight,
} from "lucide-react";
import { Panel, Metric, Tag, Modal } from "../components/ui";
import {
  number,
  filterTrades,
  tradesCSV,
  download,
  reasonName,
} from "../finance";
import type { Period, Trade } from "../types";
export default function Trades({
  period: p,
  query,
  setQuery,
  month,
  setMonth,
}: {
  period: Period;
  query: string;
  setQuery: (s: string) => void;
  month: string;
  setMonth: (s: string) => void;
}) {
  const [outcome, setOutcome] = useState("all"),
    [sort, setSort] = useState("latest"),
    [page, setPage] = useState(0),
    [trade, setTrade] = useState<Trade>();
  const filtered = useMemo(
    () =>
      filterTrades(p.trades, query, outcome, month).sort((a, b) =>
        sort === "pnl"
          ? b.pnl - a.pnl
          : sort === "loss"
            ? a.pnl - b.pnl
            : b.closed.localeCompare(a.closed),
      ),
    [p, query, outcome, month, sort],
  );
  useEffect(() => setPage(0), [p, query, outcome, month, sort]);
  const count = Math.ceil(filtered.length / 12),
    rows = filtered.slice(page * 12, (page + 1) * 12);
  return (
    <>
      <div className="trade-summary">
        <div>
          <span>已选交易</span>
          <strong>
            {filtered.length}
            <small> / {p.trades.length}</small>
          </strong>
        </div>
        <div>
          <span>已选交易净利润</span>
          <strong
            className={
              filtered.reduce((a, t) => a + t.pnl, 0) >= 0 ? "green" : "rose"
            }
          >
            {number(filtered.reduce((a, t) => a + t.pnl, 0))}
            <small> USDT</small>
          </strong>
        </div>
        <div>
          <span>选中月份</span>
          <strong>{month || "全部月份"}</strong>
        </div>
        <button
          className="button"
          onClick={() =>
            download(
              tradesCSV(filtered),
              "rcm-trades.csv",
              "text/csv;charset=utf-8",
            )
          }
        >
          <ArrowDownToLine size={15} />
          导出当前筛选
        </button>
      </div>
      <Panel
        title="原生成交账本"
        subtitle="按交易平仓时间归属 · 点击交易编号查看逐笔成交"
        action={<Tag>{p.trades.length} TRADES</Tag>}
      >
        <div className="table-toolbar">
          <label className="table-search">
            <Search size={15} />
            <input
              aria-label="搜索交易"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索编号、日期或退出原因"
            />
          </label>
          <select
            aria-label="交易类型"
            value={outcome}
            onChange={(e) => setOutcome(e.target.value)}
          >
            <option value="all">全部交易</option>
            <option value="win">盈利交易</option>
            <option value="loss">亏损交易</option>
            <option value="add">包含加仓</option>
          </select>
          <select
            aria-label="交易月份"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
          >
            <option value="">全部月份</option>
            {p.monthly.map((m) => (
              <option key={m.month}>{m.month}</option>
            ))}
          </select>
          <select
            aria-label="交易排序"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="latest">最新平仓优先</option>
            <option value="pnl">盈利金额优先</option>
            <option value="loss">亏损金额优先</option>
          </select>
        </div>
        <div className="table-scroll">
          <table className="data-table trades-table">
            <thead>
              <tr>
                <th>交易编号</th>
                <th>开仓时间 / UTC</th>
                <th>平仓时间 / UTC</th>
                <th className="align-right">盈亏 / USDT</th>
                <th className="align-right">持仓时长</th>
                <th className="align-right">入场次数</th>
                <th>退出原因</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id}>
                  <td>
                    <button className="trade-link" onClick={() => setTrade(t)}>
                      {t.id}
                      <ArrowUpRight size={12} />
                    </button>
                  </td>
                  <td className="mono">
                    {t.opened.slice(0, 16).replace("T", " ")}
                  </td>
                  <td className="mono">
                    {t.closed.slice(0, 16).replace("T", " ")}
                  </td>
                  <td
                    className={`align-right mono ${t.pnl >= 0 ? "green" : "rose"}`}
                  >
                    {t.pnl >= 0 ? "+" : ""}
                    {number(t.pnl)}
                  </td>
                  <td className="align-right mono">
                    {number(t.duration_hours, 1)}h
                  </td>
                  <td className="align-right mono">
                    {t.entries > 1 ? (
                      <Tag kind="positive">{t.entries} 次</Tag>
                    ) : (
                      "1"
                    )}
                  </td>
                  <td>
                    <span className="exit-label">{reasonName(t.reason)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && (
            <div className="empty-state">
              <Search size={24} />
              <h3>没有匹配的交易</h3>
              <p>调整月份或清除筛选，查看其他记录。</p>
              <button
                className="button"
                onClick={() => {
                  setQuery("");
                  setOutcome("all");
                  setMonth("");
                }}
              >
                清除筛选
              </button>
            </div>
          )}
        </div>
        <div className="pagination">
          <span>
            显示 {filtered.length ? page * 12 + 1 : 0}–
            {Math.min((page + 1) * 12, filtered.length)} 条，共{" "}
            {filtered.length} 条
          </span>
          <div>
            <button
              aria-label="上一页"
              className="icon-button"
              disabled={!page}
              onClick={() => setPage(page - 1)}
            >
              <ChevronLeft size={16} />
            </button>
            <span>
              {page + 1} / {Math.max(1, count)}
            </span>
            <button
              aria-label="下一页"
              className="icon-button"
              disabled={page + 1 >= count}
              onClick={() => setPage(page + 1)}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </Panel>
      {trade && (
        <Modal
          title={`${trade.id} · 成交明细`}
          close={() => setTrade(undefined)}
          wide
        >
          <div className="mini-metrics">
            <Metric
              label="净利润"
              value={number(trade.pnl)}
              detail="USDT · 已包含原始 5 bps 费用"
              tone={trade.pnl >= 0 ? "green" : "rose"}
            />
            <Metric
              label="入场均价"
              value={number(trade.entry_price)}
              detail="按成交数量加权"
            />
            <Metric
              label="成交总额"
              value={number(trade.turnover)}
              detail="USDT · 包含进出场与加仓"
            />
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>时间 / UTC</th>
                  <th>动作</th>
                  <th>数量 / BTC</th>
                  <th>价格 / USDT</th>
                  <th>金额 / USDT</th>
                </tr>
              </thead>
              <tbody>
                {trade.fills.map((f, i) => (
                  <tr key={i}>
                    <td className="mono">
                      {f.timestamp.slice(0, 19).replace("T", " ")}
                    </td>
                    <td>
                      <Tag kind={f.is_entry ? "positive" : ""}>
                        {f.is_entry ? (i === 0 ? "入场" : "加仓") : "退出"}
                      </Tag>
                    </td>
                    <td className="mono">{number(f.amount, 5)}</td>
                    <td className="mono">{number(f.price)}</td>
                    <td className="mono">{number(f.notional_usdt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="chart-footnote">
            来源：fills.csv → {trade.id} · {reasonName(trade.reason)} · 持仓{" "}
            {number(trade.duration_hours, 2)} 小时
          </p>
        </Modal>
      )}
    </>
  );
}
