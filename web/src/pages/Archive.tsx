import { useEffect, useMemo, useState } from "react";
import { ArrowUpRight, Download, Search, X } from "lucide-react";
import { Modal } from "../components/ui";
import { ASSET, REPO } from "../config";
import { download } from "../finance";
import { matchCase, statusLabel } from "../research";
import type { Chronicle, ResearchCase } from "../research";

export default function Archive({ data }: { data: Chronicle }) {
  const [query, setQuery] = useState("");
  const [family, setFamily] = useState("all");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("oldest");
  const [selected, setSelected] = useState<ResearchCase>();
  const [compare, setCompare] = useState<string[]>([]);
  const [comparing, setComparing] = useState(false);
  useEffect(() => {
    const sync = () => {
      const id = location.hash.split("/")[1];
      setSelected(data.cases.find((c) => c.id === id));
    };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, [data]);
  const filtered = useMemo(
    () =>
      data.cases
        .filter(
          (c) =>
            matchCase(c, query) &&
            (family === "all" || family === c.family) &&
            (status === "all" || status === c.status),
        )
        .sort((a, b) =>
          sort === "newest"
            ? b.date.localeCompare(a.date) || b.id.localeCompare(a.id)
            : a.date.localeCompare(b.date) || a.id.localeCompare(b.id),
        ),
    [data, query, family, status, sort],
  );
  const families = [...new Set(data.cases.map((c) => c.family))];
  const open = (c: ResearchCase) => {
    setSelected(c);
    location.hash = "archive/" + c.id;
  };
  const close = () => {
    setSelected(undefined);
    location.hash = "archive";
  };
  const toggleCompare = (id: string) =>
    setCompare((values) =>
      values.includes(id)
        ? values.filter((v) => v !== id)
        : values.length < 2
          ? [...values, id]
          : [values[1], id],
    );
  const csv = () => {
    const rows = [
      [
        "编号",
        "日期",
        "家族",
        "结论",
        "题目",
        "问题",
        "方法",
        "证据",
        "裁决",
        "认识",
      ],
      ...filtered.map((c) => [
        c.id,
        c.date,
        c.family,
        statusLabel[c.status],
        c.title,
        c.question,
        c.method,
        c.evidence,
        c.decision,
        c.lesson,
      ]),
    ];
    download(
      "\uFEFF" +
        rows
          .map((r) =>
            r.map((v) => '"' + v.replaceAll('"', '""') + '"').join(","),
          )
          .join("\r\n"),
      "rcm-research-archive.csv",
      "text/csv;charset=utf-8",
    );
  };
  return (
    <>
      <div className="archive-summary">
        <p>
          从最初的执行审计，到条件动量、状态建模与微观结构。每个节点保留当时的问题、检验方法和去留理由。
        </p>
        <div>
          <a
            href={ASSET + "research-history.md"}
            download
            className="text-link"
          >
            完整研究长文 <Download size={14} />
          </a>
          <button className="text-link" onClick={csv}>
            导出筛选 <Download size={14} />
          </button>
        </div>
      </div>
      <div className="archive-filters">
        <label className="table-search">
          <Search size={16} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="检索研究档案"
            placeholder="搜索 TFI、Bayes、加仓或研究编号…"
          />
        </label>
        <select
          aria-label="研究家族"
          value={family}
          onChange={(e) => setFamily(e.target.value)}
        >
          <option value="all">全部研究家族</option>
          {families.map((f) => (
            <option key={f}>{f}</option>
          ))}
        </select>
        <select
          aria-label="档案排序"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          <option value="oldest">按研究过程</option>
          <option value="newest">最近研究优先</option>
        </select>
      </div>
      <div className="archive-tabs" role="group" aria-label="研究结论筛选">
        {[["all", "全部"], ...Object.entries(statusLabel)].map(
          ([key, label]) => (
            <button
              key={key}
              className={status === key ? "active" : ""}
              onClick={() => setStatus(key)}
              aria-pressed={status === key}
            >
              {label}
              <span>
                {
                  data.cases.filter((c) => key === "all" || c.status === key)
                    .length
                }
              </span>
            </button>
          ),
        )}
        <span className="result-count">{filtered.length} 个结果</span>
      </div>
      <div className="archive-table-wrap">
        <table className="archive-table">
          <thead>
            <tr>
              <th className="compare-cell">比较</th>
              <th>研究节点</th>
              <th>方法</th>
              <th>结论</th>
              <th>裁决摘要</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <tr key={c.id}>
                <td className="compare-cell">
                  <input
                    type="checkbox"
                    checked={compare.includes(c.id)}
                    onChange={() => toggleCompare(c.id)}
                    aria-label={`比较 ${c.id}`}
                  />
                </td>
                <td>
                  <button className="case-title" onClick={() => open(c)}>
                    <small>
                      {c.id} / {c.date} / {c.family}
                    </small>
                    <strong>{c.title}</strong>
                  </button>
                </td>
                <td className="case-method">{c.methodLabel}</td>
                <td>
                  <span className={`status-label ${c.status}`}>
                    {statusLabel[c.status]}
                  </span>
                </td>
                <td className="case-decision">{c.decision}</td>
                <td>
                  <button
                    className="icon-button"
                    onClick={() => open(c)}
                    aria-label={`阅读 ${c.id}`}
                  >
                    <ArrowUpRight size={16} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!filtered.length && (
          <div className="empty-state">
            没有匹配的研究节点。
            <button
              onClick={() => {
                setQuery("");
                setFamily("all");
                setStatus("all");
              }}
            >
              清除筛选
            </button>
          </div>
        )}
      </div>
      <div className="archive-foot">
        <span>日期为报告或阶段归档日期；一个节点可以包含多项实验。</span>
        <a href={ASSET + "source-catalog.json"} download>
          原始文档目录 <Download size={13} />
        </a>
      </div>
      {compare.length > 0 && (
        <div className="compare-tray">
          <span>
            已选 {compare.join(" / ")}
            <small>最多同时比较两项研究</small>
          </span>
          <button
            className="button primary"
            disabled={compare.length !== 2}
            onClick={() => setComparing(true)}
          >
            比较研究
          </button>
          <button
            className="icon-button"
            aria-label="清空比较"
            onClick={() => setCompare([])}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {selected && (
        <Modal title={selected.id + " / " + selected.title} close={close} wide>
          <article className="case-detail">
            <div className="case-meta">
              <span>
                {selected.date} · {selected.family}
              </span>
              <span className={`status-label ${selected.status}`}>
                {statusLabel[selected.status]}
              </span>
            </div>
            <h2>{selected.question}</h2>
            <dl>
              {[
                ["检验方法", selected.method],
                ["观察结果", selected.evidence],
                ["研究裁决", selected.decision],
                ["留下的认识", selected.lesson],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
            <section className="case-sources">
              <h3>原始记录</h3>
              {selected.sources.map((s) => (
                <div key={s.path}>
                  <span>{s.title}</span>
                  <code>{s.path}</code>
                </div>
              ))}
              <a
                href={REPO + `/blob/main/research/notes/${selected.id}.md`}
                target="_blank"
                rel="noreferrer"
                className="text-link"
              >
                打开完整归档笔记 <ArrowUpRight size={14} />
              </a>
            </section>
            <div className="case-navigation">
              <button
                disabled={selected.id === "R01"}
                onClick={() =>
                  open(
                    data.cases[
                      data.cases.findIndex((c) => c.id === selected.id) - 1
                    ],
                  )
                }
              >
                ← 上一节点
              </button>
              <button
                disabled={selected.id === "R48"}
                onClick={() =>
                  open(
                    data.cases[
                      data.cases.findIndex((c) => c.id === selected.id) + 1
                    ],
                  )
                }
              >
                下一节点 →
              </button>
            </div>
          </article>
        </Modal>
      )}
      {comparing && (
        <Modal title="研究比较" close={() => setComparing(false)} wide>
          <div className="case-comparison">
            <div className="comparison-row">
              {compare.map((id) => {
                const c = data.cases.find((c) => c.id === id)!;
                return (
                  <div key={id}>
                    <span className={`status-label ${c.status}`}>
                      {c.id} · {statusLabel[c.status]}
                    </span>
                    <h2>{c.title}</h2>
                  </div>
                );
              })}
            </div>
            {(
              [
                ["研究问题", "question"],
                ["方法", "method"],
                ["结果", "evidence"],
                ["裁决", "decision"],
                ["认识", "lesson"],
              ] as const
            ).map(([label, key]) => (
              <div className="comparison-row" key={key}>
                {compare.map((id) => (
                  <div key={id}>
                    <span className="comparison-field">{label}</span>
                    <p>{data.cases.find((c) => c.id === id)![key]}</p>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </Modal>
      )}
    </>
  );
}
