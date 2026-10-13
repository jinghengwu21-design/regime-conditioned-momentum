import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FileText,
  Github,
  ListFilter,
  LoaderCircle,
  Search,
  ShieldCheck,
} from "lucide-react";
import { Tag, Modal } from "./components/ui";
import { date, number } from "./finance";
import type { Terminal } from "./types";
import { ASSET, REPO, pages, periods } from "./config";
import Overview from "./pages/Overview";
import Strategy from "./pages/Strategy";
import Risk from "./pages/Risk";
import Trades from "./pages/Trades";
import Agent from "./pages/Agent";
import Methodology from "./pages/Methodology";
import Evidence from "./pages/Evidence";
export default function App() {
  const [data, setData] = useState<Terminal>();
  const [loadError, setLoadError] = useState("");
  const [page, setPage] = useState(
    pages.some((p) => p.id === location.hash.slice(1))
      ? location.hash.slice(1)
      : "overview",
  );
  const [period, setPeriod] = useState("all");
  const [searchOpen, setSearchOpen] = useState(false),
    [query, setQuery] = useState("");
  const [methodOpen, setMethodOpen] = useState(false);
  const [tradeQuery, setTradeQuery] = useState(""),
    [tradeMonth, setTradeMonth] = useState("");
  const [api, setApi] = useState<{ model_configured: boolean } | null>(null);
  useEffect(() => {
    fetch(ASSET + "terminal.json")
      .then((r) => {
        if (!r.ok) throw Error("研究数据暂时不可用");
        return r.json();
      })
      .then(setData)
      .catch((e) => setLoadError(e.message));
    if (["localhost", "127.0.0.1"].includes(location.hostname))
      fetch("/api/status")
        .then((r) => (r.ok ? r.json() : null))
        .then(setApi)
        .catch(() => {});
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
    };
    const onHash = () => {
      const id = location.hash.slice(1);
      if (pages.some((p) => p.id === id)) setPage(id);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("hashchange", onHash);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("hashchange", onHash);
    };
  }, []);
  const go = (id: string) => {
    setPage(id);
    location.hash = id;
    window.scrollTo({ top: 0 });
  };
  if (!data)
    return (
      <div className="loading-screen">
        <div className="brand-mark">S</div>
        <h1>
          SARKAZ <span>RESEARCH</span>
        </h1>
        {loadError ? (
          <>
            <p>{loadError}</p>
            <button onClick={() => location.reload()}>重新加载</button>
          </>
        ) : (
          <>
            <LoaderCircle className="spin" />
            <p>读取研究账本与数据指纹</p>
          </>
        )}
      </div>
    );
  const current = data.periods[period],
    selectedPage = pages.find((p) => p.id === page)!;
  const monthlyOpen = (month: string) => {
    setTradeMonth(month);
    setTradeQuery("");
    go("trades");
  };
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳至研究内容
      </a>
      <aside className="sidebar">
        <a href="#overview" className="brand" onClick={() => go("overview")}>
          <svg viewBox="0 0 32 32" aria-hidden="true">
            <path d="M4 23 16 4h11L15 23ZM5 28h22" />
          </svg>
          <div>
            SARKAZ<span>RESEARCH TERMINAL</span>
          </div>
        </a>
        <div className="workspace-switch">
          <span className="workspace-avatar">S</span>
          <div>
            量化研究工作区<small>Strategy intelligence</small>
          </div>
          <ChevronDown size={13} />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="主导航">
          {pages.slice(0, 4).map((p) => (
            <button
              key={p.id}
              className={page === p.id ? "nav-item active" : "nav-item"}
              onClick={() => go(p.id)}
              aria-current={page === p.id ? "page" : undefined}
            >
              <p.icon size={17} />
              <span>{p.label}</span>
              {page === p.id && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="nav-label">RESEARCH OPERATIONS</div>
        <nav aria-label="研究工具">
          {pages.slice(4).map((p) => (
            <button
              key={p.id}
              className={page === p.id ? "nav-item active" : "nav-item"}
              onClick={() => go(p.id)}
              aria-current={page === p.id ? "page" : undefined}
            >
              <p.icon size={17} />
              <span>{p.label}</span>
              {p.id === "agent" && <span className="nav-count">5</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="dataset-status">
            <span className="status-dot" />
            <div>
              冻结研究数据<small>AS OF 03 OCT 2026 · UTC</small>
            </div>
            <ShieldCheck size={16} />
          </div>
          <a href={REPO} target="_blank" rel="noreferrer">
            <Github size={16} /> Source repository <ArrowUpRight size={14} />
          </a>
          <div className="sidebar-version">
            <span>SARKAZ V3F</span>
            <span>v2.0</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            研究工作区 <ChevronRight size={13} />
            <strong>{selectedPage.label}</strong>
          </div>
          <div className="topbar-right">
            <button
              className="search-trigger"
              aria-label="搜索研究与交易"
              onClick={() => {
                setSearchOpen(true);
                setQuery("");
              }}
            >
              <Search size={14} />
              <span>搜索研究与交易</span>
              <kbd>Ctrl K</kbd>
            </button>
            <button
              className="icon-button"
              title="计算口径"
              aria-label="查看计算口径"
              onClick={() => setMethodOpen(true)}
            >
              <CircleHelp size={18} />
            </button>
            <span className="avatar">JW</span>
          </div>
        </header>
        <main id="main-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                SARKAZ V3F <span>/</span> {selectedPage.en.toUpperCase()}
              </div>
              <h1>
                {page === "overview"
                  ? "策略表现，一览全局。"
                  : selectedPage.label}
              </h1>
              <p>
                {
                  (
                    {
                      overview:
                        "从收益曲线到每一笔成交，理解策略如何承担风险、创造收益。",
                      strategy:
                        "BTC 永续 · 5 分钟动量 · 单向做多 · 冻结规则研究",
                      risk: "观察回撤、收益集中度，以及固定成交路径下的成本敏感性。",
                      trades: "逐笔检查交易结果，追溯入场、加仓与退出成交。",
                      agent:
                        "研究工具、结构化结论与独立复核，形成可检查的运行链路。",
                      evidence:
                        "统一来源、时间边界与指标定义，让研究结果可以复现。",
                    } as Record<string, string>
                  )[page]
                }
              </p>
            </div>
            <div className="heading-actions">
              <Tag>
                <span className="status-dot" />
                历史回测
              </Tag>
              <a
                className="button primary"
                href={ASSET + "report.html"}
                target="_blank"
                rel="noreferrer"
              >
                <FileText size={15} />
                研究报告
                <ArrowUpRight size={14} />
              </a>
            </div>
          </div>
          {page !== "agent" && page !== "evidence" && (
            <div className="scope-bar">
              <div className="asset-chip">
                <span className="bitcoin">₿</span>
                <strong>BTC / USDT</strong>
                <span>PERP</span>
                <i />
                <span>Sarkaz V3F</span>
              </div>
              <div className="period-switch" aria-label="研究区间">
                {periods.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => {
                      setPeriod(p.id);
                      setTradeMonth("");
                    }}
                    className={period === p.id ? "selected" : ""}
                    aria-pressed={period === p.id}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <button
                className="scope-dates"
                onClick={() => setMethodOpen(true)}
              >
                {date(current.base.scope.start)} —{" "}
                {date(current.base.scope.end_exclusive)}
                <CircleHelp size={12} />
              </button>
            </div>
          )}
          {page === "overview" && (
            <Overview
              period={current}
              periodKey={period}
              onMonth={monthlyOpen}
              go={go}
            />
          )}
          {page === "strategy" && <Strategy period={current} go={go} />}
          {page === "risk" && <Risk period={current} />}
          {page === "trades" && (
            <Trades
              period={current}
              query={tradeQuery}
              setQuery={setTradeQuery}
              month={tradeMonth}
              setMonth={setTradeMonth}
            />
          )}
          {page === "agent" && <Agent api={api} />}
          {page === "evidence" && <Evidence data={data} />}
          <footer>
            <span>
              SARKAZ RESEARCH <i /> BTC 永续策略研究
            </span>
            <span>
              平仓权益 · 单边 5 bps · 资金费未计{" "}
              <button onClick={() => setMethodOpen(true)}>
                计算口径 <ArrowUpRight size={11} />
              </button>
            </span>
          </footer>
        </main>
      </div>
      {methodOpen && (
        <Modal title="研究口径" close={() => setMethodOpen(false)}>
          <Methodology />
        </Modal>
      )}
      {searchOpen && (
        <Modal title="搜索工作区" close={() => setSearchOpen(false)}>
          <div className="command-input">
            <Search size={18} />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="页面名称、交易编号或日期，如 T0900"
              aria-label="搜索工作区内容"
            />
          </div>
          <div className="command-results">
            {pages
              .filter(
                (p) =>
                  !query ||
                  (p.label + p.en).toLowerCase().includes(query.toLowerCase()),
              )
              .map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    go(p.id);
                    setSearchOpen(false);
                  }}
                >
                  <p.icon size={16} />
                  {p.label}
                  <ArrowRight size={14} />
                </button>
              ))}
            {query &&
              data.periods[period].trades
                .filter((t) =>
                  `${t.id} ${t.closed}`
                    .toLowerCase()
                    .includes(query.toLowerCase()),
                )
                .slice(0, 6)
                .map((t) => (
                  <button
                    key={t.id}
                    onClick={() => {
                      setTradeQuery(t.id);
                      setTradeMonth("");
                      go("trades");
                      setSearchOpen(false);
                    }}
                  >
                    <ListFilter size={16} />
                    {t.id}
                    <span>
                      {date(t.closed)} · {number(t.pnl)} USDT
                    </span>
                  </button>
                ))}
            {query &&
              !pages.some((p) =>
                (p.label + p.en).toLowerCase().includes(query.toLowerCase()),
              ) &&
              !data.periods[period].trades.some((t) =>
                `${t.id} ${t.closed}`
                  .toLowerCase()
                  .includes(query.toLowerCase()),
              ) && (
                <div className="empty-state">
                  没有匹配结果。可尝试“风险”或“T0900”。
                </div>
              )}
          </div>
        </Modal>
      )}
    </div>
  );
}
