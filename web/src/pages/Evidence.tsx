import {
  Database,
  FileText,
  ArrowDownToLine,
  ArrowUpRight,
  ChevronDown,
  Layers,
  BookOpen,
  ShieldCheck,
} from "lucide-react";
import { Panel, Tag } from "../components/ui";
import { number } from "../finance";
import { ASSET, REPO } from "../config";
import type { Terminal } from "../types";
import Methodology from "./Methodology";
export default function Evidence({ data }: { data: Terminal }) {
  return (
    <>
      <div className="data-banner">
        <div>
          <Database size={28} />
          <h2>一个数据版本，一套计算口径。</h2>
          <p className="mono">{data.manifest.dataset_id}</p>
        </div>
        <div className="dataset-counts">
          <div>
            <strong>922</strong>
            <span>历史交易</span>
          </div>
          <div>
            <strong>2,247</strong>
            <span>成交记录</span>
          </div>
          <div>
            <strong>2,467</strong>
            <span>完整 UTC 日</span>
          </div>
        </div>
      </div>
      <div className="two-columns evidence-columns">
        <Panel title="数据文件" subtitle="研究账本与计算附件">
          <div className="file-list">
            {Object.entries(data.manifest.files).map(([name, meta]) => (
              <div key={name}>
                <span className="file-icon">
                  <FileText size={19} />
                </span>
                <div>
                  <strong>{name}</strong>
                  <small>{number(meta.bytes / 1024, 1)} KB</small>
                </div>
                {["trades.csv", "fills.csv"].includes(name) ? (
                  <a
                    href={ASSET + name}
                    download
                    aria-label={`下载 ${name}`}
                    className="icon-button"
                  >
                    <ArrowDownToLine size={16} />
                  </a>
                ) : (
                  <a
                    href={REPO + "/blob/main/data/" + name}
                    target="_blank"
                    rel="noreferrer"
                    className="icon-button"
                    aria-label={`查看 ${name}`}
                  >
                    <ArrowUpRight size={16} />
                  </a>
                )}
              </div>
            ))}
          </div>
          <div className="panel-bottom">
            <a href={ASSET + "manifest.json"} download className="text-link">
              下载数据清单 <ArrowDownToLine size={13} />
            </a>
            <a
              href={REPO + "/blob/main/data/DATA_CARD.md"}
              target="_blank"
              rel="noreferrer"
              className="text-link"
            >
              Data card <ArrowUpRight size={13} />
            </a>
          </div>
          <div className="panel-bottom">
            <a href={ASSET + "result.json"} download className="text-link">
              报告运行结果 <ArrowDownToLine size={13} />
            </a>
            <a href={ASSET + "trace.jsonl"} download className="text-link">
              完整调用轨迹 <ArrowDownToLine size={13} />
            </a>
          </div>
        </Panel>
        <Panel title="计算方法" subtitle="从原始 CSV 到最终结论">
          <Methodology />
        </Panel>
      </div>
      <Panel title="研究来源" subtitle="明确记录来源与证据标识">
        <div className="evidence-list">
          {data.evidence.map((e) => (
            <details key={e.id}>
              <summary>
                <Tag>{e.id}</Tag>
                <strong>{e.title}</strong>
                <ChevronDown size={15} />
              </summary>
              <p>{e.text}</p>
              <div>
                <span>来源</span>
                <code>{e.source}</code>
              </div>
            </details>
          ))}
        </div>
      </Panel>
      <div className="resource-links">
        <a
          href={REPO + "/blob/main/docs/ARCHITECTURE.md"}
          target="_blank"
          rel="noreferrer"
        >
          <Layers size={19} />
          <div>
            系统架构<small>数据、计算、Agent 与审计</small>
          </div>
          <ArrowUpRight size={16} />
        </a>
        <a
          href={REPO + "/blob/main/docs/BENCHMARKS.md"}
          target="_blank"
          rel="noreferrer"
        >
          <BookOpen size={19} />
          <div>
            设计参考<small>开源研究与架构取舍</small>
          </div>
          <ArrowUpRight size={16} />
        </a>
        <a href={REPO + "/actions"} target="_blank" rel="noreferrer">
          <ShieldCheck size={19} />
          <div>
            持续集成<small>数值、接口与构建检查</small>
          </div>
          <ArrowUpRight size={16} />
        </a>
      </div>
    </>
  );
}
