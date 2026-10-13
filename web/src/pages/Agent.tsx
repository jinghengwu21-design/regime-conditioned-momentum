import { useState, useEffect } from "react";
import {
  Check,
  LoaderCircle,
  Play,
  TerminalSquare,
  ShieldCheck,
  ChevronRight,
  ArrowRight,
  Database,
  ArrowDownToLine,
} from "lucide-react";
import { Panel, Tag } from "../components/ui";
import { date, percent, download } from "../finance";
import { ASSET, scenarios } from "../config";
import type { Run } from "../types";
export default function Agent({
  api,
}: {
  api: { model_configured: boolean } | null;
}) {
  const [recordings, setRecordings] = useState<Record<string, Run>>(),
    [error, setError] = useState("");
  const [scenario, setScenario] = useState("numeric_mismatch"),
    [live, setLive] = useState<Run>(),
    [busy, setBusy] = useState(false);
  const [event, setEvent] = useState(0),
    [io, setIo] = useState("output"),
    [mode, setMode] = useState("offline");
  const [question, setQuestion] = useState(
    "BTC 动量策略提高交易成本后，收益和回撤如何变化？",
  );
  const [start, setStart] = useState("2020-01-01T00:00");
  const [end, setEnd] = useState("2026-10-03T12:05");
  const [fee, setFee] = useState(5);
  useEffect(() => {
    fetch(ASSET + "experiments.json")
      .then((r) => {
        if (!r.ok) throw Error("实验记录暂时不可用");
        return r.json();
      })
      .then(setRecordings)
      .catch((e) => setError(e.message));
  }, []);
  const run = live || recordings?.[scenario];
  const execute = async () => {
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          scenario,
          mode,
          start: start + ":00Z",
          end_exclusive: end + ":00Z",
          fee_bps: fee,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw Error(result.error);
      setLive(result);
      setEvent(0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "研究执行失败");
    } finally {
      setBusy(false);
    }
  };
  const chosen = scenarios.find((s) => s.id === scenario)!;
  const selected = run?.trace[Math.min(event, run.trace.length - 1)];
  return (
    <>
      <div className="agent-layout">
        <div className="experiment-config">
          <div className="eyebrow">EXPERIMENT DESIGN</div>
          <h2>观察系统如何处理偏差</h2>
          <p>每个实验保留输入、原始结论、工具输出与最终复核。</p>
          <div className="scenario-list">
            {scenarios.map((s) => (
              <button
                key={s.id}
                className={scenario === s.id ? "selected" : ""}
                onClick={() => {
                  setScenario(s.id);
                  setLive(undefined);
                  setEvent(0);
                  setError("");
                }}
              >
                <span className="scenario-radio" />
                <div>
                  {s.name}
                  <small>{s.text}</small>
                </div>
                {scenario === s.id && <Check size={15} />}
              </button>
            ))}
          </div>
          {api && (
            <div className="run-form">
              <label>
                研究资产
                <input value="BTC / USDT · 永续" readOnly />
              </label>
              <label>
                研究问题
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  maxLength={600}
                />
              </label>
              <label>
                起始时间 · UTC
                <input
                  type="datetime-local"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                />
              </label>
              <label>
                结束时间 · UTC · 不含
                <input
                  type="datetime-local"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                />
              </label>
              <label>
                单边手续费 · bps
                <input
                  type="number"
                  min="0"
                  max="50"
                  step="0.5"
                  value={fee}
                  onChange={(e) => setFee(+e.target.value)}
                />
              </label>
              <label>
                执行模式
                <select value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="offline">确定性研究</option>
                  <option value="openai" disabled={!api.model_configured}>
                    模型工具调用{!api.model_configured ? " · 未配置" : ""}
                  </option>
                </select>
              </label>
              <button
                className="button primary"
                disabled={
                  busy ||
                  question.length < 5 ||
                  !start ||
                  !end ||
                  start >= end ||
                  fee < 0 ||
                  fee > 50
                }
                onClick={execute}
              >
                {busy ? (
                  <LoaderCircle size={15} className="spin" />
                ) : (
                  <Play size={15} />
                )}{" "}
                {busy ? "研究执行中" : "运行实验"}
              </button>
            </div>
          )}
          <div className="mode-note">
            <TerminalSquare size={16} />
            <p>
              {api
                ? "本地 Python 服务已连接，可执行新的研究与故障注入。"
                : "公开站点展示已归档的真实运行。启动本地服务可新建研究与执行故障注入。"}
            </p>
          </div>
        </div>
        <div className="experiment-main">
          {error && (
            <div role="alert" className="error-box">
              {error}
            </div>
          )}
          {!run ? (
            <div className="loading-panel">
              <LoaderCircle className="spin" />
              <span>读取实验记录</span>
            </div>
          ) : (
            <>
              <div className="run-header">
                <div>
                  <div className="eyebrow">
                    {live ? "LOCAL EXECUTION" : "RECORDED EXECUTION"}
                  </div>
                  <h2>{chosen.name}</h2>
                  <span className="mono">{run.run_id}</span>
                </div>
                <Tag kind={run.reviews.at(-1)?.passed ? "positive" : "warning"}>
                  <ShieldCheck size={13} />
                  {run.reviews.at(-1)?.passed ? "复核通过" : "复核未通过"}
                </Tag>
              </div>
              <p className="chart-footnote">
                {run.request.asset} · {date(run.request.start)} 至{" "}
                {date(run.request.end_exclusive)} UTC（右端不含） · 单边{" "}
                {run.request.fee_bps} bps
              </p>
              <div className="flow-strip">
                {[
                  "规划",
                  "上下文",
                  "工具分析",
                  "独立复核",
                  ...(run.repaired ? ["结论修正", "再次复核"] : []),
                  "报告",
                ].map((s, i) => (
                  <div key={i} className={s === "结论修正" ? "repair" : ""}>
                    <Check size={12} />
                    {s}
                    {i < (run.repaired ? 6 : 4) && <ChevronRight size={13} />}
                  </div>
                ))}
              </div>
              <div className="experiment-results">
                <div>
                  <span>数值核验</span>
                  <strong>
                    {run.reviews.at(-1)!.checked_claims}
                    <small>项已核验</small>
                  </strong>
                </div>
                <div>
                  <span>复核轮次</span>
                  <strong>
                    {run.reviews.length}
                    <small>{run.repaired ? "已触发修正" : "一次通过"}</small>
                  </strong>
                </div>
                <div>
                  <span>工具调用</span>
                  <strong>
                    {
                      run.trace.filter((t) =>
                        [
                          "read_market",
                          "read_backtest",
                          "calculate_metrics",
                          "compare_costs",
                          "search_evidence",
                          "read_evidence",
                        ].includes(t.action),
                      ).length
                    }
                    <small>次</small>
                  </strong>
                </div>
              </div>
              {scenario === "numeric_mismatch" && (
                <div className="numeric-diff">
                  <div>
                    <span>原始结论 / 被拒绝</span>
                    <strong className="rose">
                      {percent(
                        run.original_draft.claims.find(
                          (c) => c.metric === "total_return",
                        )!.value,
                      )}
                    </strong>
                  </div>
                  <ArrowRight size={22} />
                  <div>
                    <span>独立复算 / 最终结论</span>
                    <strong className="green">
                      {percent(
                        run.draft.claims.find(
                          (c) => c.metric === "total_return",
                        )!.value,
                      )}
                    </strong>
                  </div>
                  <Tag kind="positive">证据绑定修正</Tag>
                </div>
              )}
              {scenario === "prompt_injection" && (
                <div className="outcome-message">
                  <ShieldCheck size={18} />
                  外部资料隔离：{run.external.quarantined
                    ? "已隔离"
                    : "未触发"}{" "}
                  · 最终数值与冻结账本一致
                </div>
              )}
              {scenario === "missing_data" && (
                <div className="outcome-message">
                  <Database size={18} />
                  检测到 {run.market.coverage.missing_days} 个缺失日 ·
                  缺口未插值
                </div>
              )}
              {scenario === "tool_abuse" && (
                <div className="outcome-message">
                  <ShieldCheck size={18} />
                  execute_shell 请求被拒绝 · 研究通过注册工具继续执行
                </div>
              )}
              <Panel
                title="运行轨迹"
                subtitle={`${date(run.recorded_at_utc)} ${run.recorded_at_utc.slice(11, 19)} UTC · ${run.mode === "offline" ? "确定性研究" : "模型研究"}`}
                action={
                  <button
                    className="micro-button"
                    onClick={() =>
                      download(
                        run.trace.map((t) => JSON.stringify(t)).join("\n"),
                        `${run.run_id}.jsonl`,
                        "application/x-ndjson",
                      )
                    }
                  >
                    <ArrowDownToLine size={13} />
                    JSONL
                  </button>
                }
              >
                <div className="trace-grid">
                  <div className="trace-list">
                    {run.trace.map((t, i) => (
                      <button
                        className={event === i ? "selected" : ""}
                        key={i}
                        onClick={() => setEvent(i)}
                      >
                        <span className={`event-dot ${t.status}`} />
                        <span>
                          {t.action}
                          <small>
                            {t.node} · {t.status}
                          </small>
                        </span>
                        <em>{t.elapsed_ms.toFixed(0)}ms</em>
                      </button>
                    ))}
                  </div>
                  <div className="trace-detail">
                    <div className="trace-detail-head">
                      <strong>{selected?.action}</strong>
                      <div className="segmented">
                        <button
                          className={io === "input" ? "selected" : ""}
                          onClick={() => setIo("input")}
                        >
                          输入
                        </button>
                        <button
                          className={io === "output" ? "selected" : ""}
                          onClick={() => setIo("output")}
                        >
                          输出
                        </button>
                      </div>
                    </div>
                    <pre>
                      {JSON.stringify(
                        io === "input" ? selected?.input : selected?.output,
                        null,
                        2,
                      )}
                    </pre>
                    <div className="trace-hash">
                      SHA-256{" "}
                      <code>{selected?.output_sha256.slice(0, 24)}…</code>
                    </div>
                  </div>
                </div>
              </Panel>
              <Panel
                title="研究结论"
                subtitle="最终结构化结论 · 证据编号随运行保留"
                action={
                  <button
                    className="micro-button"
                    onClick={() =>
                      download(
                        JSON.stringify(run, null, 2),
                        `${run.run_id}.json`,
                        "application/json",
                      )
                    }
                  >
                    <ArrowDownToLine size={13} />
                    运行结果
                  </button>
                }
              >
                <div className="research-conclusion">
                  <p>{run.draft.summary}</p>
                  <ul>
                    {run.draft.findings.map((finding, i) => (
                      <li key={i}>{finding}</li>
                    ))}
                  </ul>
                </div>
              </Panel>
            </>
          )}
        </div>
      </div>
    </>
  );
}
