"""Publish the curated research archive as Markdown, CSV and browser data."""
import csv
import io
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"retained": "保留", "rejected": "淘汰", "diagnostic": "研究保留", "parked": "暂缓"}

def main():
    data = json.loads((ROOT / "research/chronicle.json").read_text(encoding="utf-8"))
    notes = ROOT / "research/notes"
    notes.mkdir(exist_ok=True)
    introduction = (ROOT / "research/INTRO.md").read_text(encoding="utf-8")
    sections = [introduction, "\n## 决策节点\n"]
    csv_file = io.StringIO(newline="")
    writer = csv.writer(csv_file)
    writer.writerow(["id", "date", "family", "status", "title", "question", "method", "evidence", "decision", "lesson"])
    for c in data["cases"]:
        if not c["sources"]:
            raise ValueError(f"Research source missing: {c['id']}")
        heading = f"{c['id']} · {c['title']}"
        body = f"\n{c['date']} · {c['family']} · {LABELS[c['status']]} · {c['methodLabel']}\n"
        for title, key in [("研究问题", "question"), ("检验方法", "method"), ("观察结果", "evidence"), ("研究裁决", "decision"), ("留下的认识", "lesson")]:
            body += f"\n**{title}**\n\n{c[key]}\n"
        body += "\n**原始记录**\n\n" + "\n".join(f"- `{s['path']}`" for s in c["sources"]) + "\n"
        (notes / (c["id"] + ".md")).write_text("# " + heading + "\n" + body + "\n[研究全史](../../docs/RESEARCH_HISTORY.md) · [研究目录](../README.md)\n", encoding="utf-8")
        sections.append("\n### " + heading + "\n" + body)
        writer.writerow([c[k] for k in ["id", "date", "family", "status", "title", "question", "method", "evidence", "decision", "lesson"]])
    history = "\n".join(sections)
    (ROOT / "docs/RESEARCH_HISTORY.md").write_text(history, encoding="utf-8")
    (ROOT / "research/decisions.csv").write_text(csv_file.getvalue(), encoding="utf-8-sig", newline="")
    catalog = "# 研究档案\n\n" + data["name"] + " 的研究节点、源文档目录与方法综述。\n\n[完整研究过程](../docs/RESEARCH_HISTORY.md) · [策略规格](../docs/STRATEGY.md) · [Agent 研究方法](../docs/AGENT_RESEARCH.md)\n\n"
    catalog += "`chronicle.json` 是决策档案的数据源；`INTRO.md` 是研究综述；`notes/`、CSV 和网站数据由 `python scripts/build_research.py` 生成。`source-catalog.json` 保留 2026-10-03 原研究工作区的文档目录，包含历史副本。目录条目与独立实验数量不同。\n\n| 编号 | 研究节点 | 家族 | 裁决 |\n|---|---|---|---|\n"
    catalog += "\n".join(f"| {c['id']} | [{c['title']}](notes/{c['id']}.md) | {c['family']} | {LABELS[c['status']]} |" for c in data["cases"]) + "\n"
    (ROOT / "research/README.md").write_text(catalog, encoding="utf-8")
    public = ROOT / "web/public/data"
    public.mkdir(parents=True, exist_ok=True)
    for name in ["chronicle.json", "source-catalog.json", "decisions.csv"]:
        shutil.copy2(ROOT / "research" / name, public / name)
    (public / "research-history.md").write_text(history, encoding="utf-8")
    print(f"Built {len(data['cases'])} research notes, history, CSV and browser assets.")

if __name__ == "__main__":
    main()
