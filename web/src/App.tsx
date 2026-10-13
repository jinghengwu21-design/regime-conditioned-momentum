import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Github,
  LoaderCircle,
  Search,
  FileText,
} from "lucide-react";
import { Modal } from "./components/ui";
import { date, number } from "./finance";
import type { Terminal } from "./types";
import type { Chronicle } from "./research";
import { matchCase } from "./research";
import { ASSET, REPO, pages, periods } from "./config";
import Overview from "./pages/Overview";
import Research from "./pages/Research";
import Archive from "./pages/Archive";
import Process from "./pages/Process";
import Strategy from "./pages/Strategy";
import Risk from "./pages/Risk";
import Trades from "./pages/Trades";
import Methodology from "./pages/Methodology";
import Evidence from "./pages/Evidence";

function route() {
  const id = location.hash.slice(1).split("/")[0];
  return id === "overview"
    ? "research"
    : id === "agent"
      ? "process"
      : pages.some((p) => p.id === id)
        ? id
        : "research";
}
const descriptions: Record<string, string> = {
  strategy: "从实际规则、研究对照与收益结构，解释最终保留的条件动量策略。",
  archive: "研究问题、失败原因与保留依据，按开发过程组织的决策档案。",
  process: "研究讨论、因子探索、原生回测与实验记忆如何形成一个循环。",
  performance: "连续账户、市场基准、回撤路径与逐月收益。",
  risk: "交易成本、收益集中度与回撤恢复，观察同一策略的不同压力情景。",
  trades: "从账户结果下钻到每一笔入场、加仓与退出。",
  evidence: "研究数据、计算口径、代码来源与可复现分析。",
};
export default function App() {
  const [data, setData] = useState<Terminal>();
  const [research, setResearch] = useState<Chronicle>();
  const [loadError, setLoadError] = useState("");
  const [page, setPage] = useState(route);
  const [period, setPeriod] = useState("all");
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [methodOpen, setMethodOpen] = useState(false);
  const [tradeQuery, setTradeQuery] = useState("");
  const [tradeMonth, setTradeMonth] = useState("");
  const [api, setApi] = useState<{ model_configured: boolean } | null>(null);
  useEffect(() => {
    async function read<T>(name: string): Promise<T> {
      const r = await fetch(ASSET + name);
      if (!r.ok) throw new Error("研究数据暂时不可用");
      return r.json();
    }
    Promise.all([
      read<Terminal>("terminal.json"),
      read<Chronicle>("chronicle.json"),
    ])
      .then(([t, c]) => {
        setData(t);
        setResearch(c);
      })
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
    const onHash = () => setPage(route());
    window.addEventListener("keydown", onKey);
    window.addEventListener("hashchange", onHash);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("hashchange", onHash);
    };
  }, []);
  useEffect(() => {
    document.title = `RCM · ${pages.find((p) => p.id === page)?.label || "Regime-Conditioned Momentum"}`;
  }, [page]);
  const go = (id: string) => {
    location.hash = id;
    setPage(id.split("/")[0]);
    window.scrollTo({ top: 0 });
  };
  if (!data || !research)
    return (
      <div className="loading-screen">
        <div className="wordmark">
          RCM<span>RESEARCH</span>
        </div>
        {loadError ? (
          <>
            <p>{loadError}</p>
            <button className="button" onClick={() => location.reload()}>
              重新加载
            </button>
          </>
        ) : (
          <>
            <LoaderCircle className="spin" />
            <p>读取研究档案与交易账本</p>
          </>
        )}
      </div>
    );
  const selectedPage = pages.find((p) => p.id === page)!;
  const current = data.periods[period];
  const financial = ["performance", "risk", "trades"].includes(page);
  const monthlyOpen = (month: string) => {
    setTradeMonth(month);
    setTradeQuery("");
    go("trades");
  };
  const foundCases = query
    ? research.cases.filter((c) => matchCase(c, query)).slice(0, 6)
    : [];
  const foundPages = pages.filter(
    (p) =>
      !query || (p.label + p.en).toLowerCase().includes(query.toLowerCase()),
  );
  const foundTrades = query
    ? current.trades
        .filter((t) =>
          `${t.id} ${t.closed}`.toLowerCase().includes(query.toLowerCase()),
        )
        .slice(0, 4)
    : [];
  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        跳至研究内容
      </a>
      <header className="masthead">
        <div className="masthead-inner">
          <a
            className="wordmark"
            href="#research"
            onClick={() => go("research")}
          >
            RCM<span>RESEARCH</span>
          </a>
          <span className="masthead-title">REGIME-CONDITIONED MOMENTUM</span>
          <div className="masthead-actions">
            <button
              className="search-trigger"
              aria-label="搜索研究与交易"
              onClick={() => {
                setSearchOpen(true);
                setQuery("");
              }}
            >
              <Search size={16} />
              <span>搜索研究</span>
              <kbd>⌘ K</kbd>
            </button>
            <a
              href={REPO}
              target="_blank"
              rel="noreferrer"
              aria-label="GitHub 源代码"
            >
              <Github size={18} />
            </a>
          </div>
        </div>
        <nav className="main-nav" aria-label="主导航">
          {pages.map((p) => (
            <button
              key={p.id}
              className={page === p.id ? "active" : ""}
              onClick={() => go(p.id)}
              aria-current={page === p.id ? "page" : undefined}
            >
              {p.label}
              {p.id === "archive" && <small>{research.cases.length}</small>}
            </button>
          ))}
          <span className="nav-edition">RESEARCH EDITION · 03</span>
        </nav>
      </header>
      <main
        id="main-content"
        tabIndex={-1}
        className={page === "research" ? "home-page" : "content-page"}
      >
        {page !== "research" && (
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                RCM RESEARCH / {selectedPage.en.toUpperCase()}
              </div>
              <h1>{selectedPage.label}</h1>
              <p>{descriptions[page]}</p>
            </div>
            <a
              className="text-link"
              href={REPO + "/blob/main/docs/RESEARCH_HISTORY.md"}
              target="_blank"
              rel="noreferrer"
            >
              <FileText size={15} />
              研究长文 <ArrowUpRight size={13} />
            </a>
          </div>
        )}
        {financial && (
          <div className="scope-bar">
            <div className="asset-chip">
              <strong>BTC / USDT</strong>
              <span>PERP · RCM-3F</span>
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
            <button className="scope-dates" onClick={() => setMethodOpen(true)}>
              {date(current.base.scope.start)} —{" "}
              {date(current.base.scope.end_exclusive)}{" "}
              <ArrowUpRight size={12} />
            </button>
          </div>
        )}
        {page === "research" && (
          <Research data={research} period={data.periods.all} go={go} />
        )}
        {page === "strategy" && <Strategy period={data.periods.all} go={go} />}
        {page === "archive" && <Archive data={research} />}
        {page === "process" && <Process data={research} go={go} api={api} />}
        {page === "performance" && (
          <Overview
            period={current}
            periodKey={period}
            onMonth={monthlyOpen}
            go={go}
          />
        )}
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
        {page === "evidence" && <Evidence data={data} />}
        <footer>
          <div className="footer-brand">
            RCM<span>Regime-Conditioned Momentum</span>
          </div>
          <p>
            独立策略研究 · 数据截至 2026.10.03
            <br />
            研究回测 · 平仓权益 · 单边 5 bps · 资金费未计
          </p>
          <div>
            <button onClick={() => setMethodOpen(true)}>
              计算口径 <ArrowUpRight size={12} />
            </button>
            <a href={REPO} target="_blank" rel="noreferrer">
              Source <ArrowUpRight size={12} />
            </a>
          </div>
        </footer>
      </main>
      {methodOpen && (
        <Modal title="研究口径" close={() => setMethodOpen(false)}>
          <Methodology />
        </Modal>
      )}
      {searchOpen && (
        <Modal title="搜索研究与交易" close={() => setSearchOpen(false)}>
          <div className="command-input">
            <Search size={18} />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="研究方法、失败原因、R14 或 T0900"
              aria-label="搜索工作区内容"
            />
          </div>
          <div className="command-results">
            {foundPages.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  go(p.id);
                  setSearchOpen(false);
                }}
              >
                <span className="search-category">页面</span>
                {p.label}
                <ArrowRight size={14} />
              </button>
            ))}
            {foundCases.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  go("archive/" + c.id);
                  setSearchOpen(false);
                }}
              >
                <span className="search-category">{c.id}</span>
                <span>
                  {c.title}
                  <small>
                    {c.family} · {c.methodLabel}
                  </small>
                </span>
                <ArrowUpRight size={14} />
              </button>
            ))}
            {foundTrades.map((t) => (
              <button
                key={t.id}
                onClick={() => {
                  setTradeQuery(t.id);
                  setTradeMonth("");
                  go("trades");
                  setSearchOpen(false);
                }}
              >
                <span className="search-category">交易</span>
                {t.id}
                <span>
                  {date(t.closed)} · {number(t.pnl)} USDT
                </span>
              </button>
            ))}
            {!foundCases.length &&
              !foundPages.length &&
              !foundTrades.length && (
                <div className="empty-state">没有匹配的研究或交易。</div>
              )}
          </div>
        </Modal>
      )}
    </div>
  );
}
