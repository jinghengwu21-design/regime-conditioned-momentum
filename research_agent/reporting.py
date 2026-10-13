from __future__ import annotations

import html
import json

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .models import METRIC_INFO, format_metric


def equity_figure(result: dict, height=400):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.055, row_heights=[0.78, 0.22])
    rows = result["base"]["curve"]
    fig.add_trace(go.Scatter(x=[r["date"] for r in rows], y=[r["equity"] for r in rows], mode="lines", line={"color": "#087f75", "width": 2.5, "shape": "hv"}, name="已实现权益 · USDT", hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.2f} USDT<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=[r["date"] for r in rows], y=[-r["drawdown"] for r in rows], mode="lines", line={"color": "#d49a56", "width": 1, "shape": "hv"}, fill="tozeroy", fillcolor="rgba(212,154,86,0.16)", name="已实现回撤", hovertemplate="%{y:.2%}<extra></extra>"), row=2, col=1)
    fig.update_layout(height=height, margin={"t": 15, "l": 5, "r": 15, "b": 5}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"family": "Segoe UI, Microsoft YaHei, sans-serif", "color": "#506272"}, showlegend=False)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e8edf0", row=1, col=1)
    fig.update_yaxes(tickformat=".0%", gridcolor="#e8edf0", row=2, col=1)
    return fig


def cost_figure(result: dict, height=340):
    fig = go.Figure()
    colors = ["#087f75", "#6685ab", "#d49a56", "#a1698b"]
    for i, scenario in enumerate(result["costs"]):
        curve = scenario["curve"]
        fig.add_trace(go.Scatter(x=[r["date"] for r in curve], y=[r["equity"] for r in curve], name=f"单边 {scenario['fee_bps']:g} bps", line={"color": colors[i % len(colors)], "width": 2, "shape": "hv"}))
    fig.update_layout(height=height, margin={"t": 20, "l": 5, "r": 10, "b": 5}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend={"orientation": "h", "y": 1.12}, font={"color": "#506272"})
    fig.update_yaxes(gridcolor="#e8edf0", title="权益 USDT")
    fig.update_xaxes(showgrid=False)
    return fig


def render_markdown(result: dict) -> str:
    r, b, m = result["request"], result["base"], result["base"]["metrics"]
    lines = ["# Sarkaz V3F · 绩效与成本研究", "", f"**研究问题：** {r['question']}", "", f"运行：`{result['run_id']}` · {result['execution_label']} · 记录时间 {result['recorded_at_utc']}", "", f"资产：{r['asset']}；实际统计区间 [{b['scope']['start']}, {b['scope']['end_exclusive']})，UTC。", f"单边手续费 {r['fee_bps']:g} bps，逐成交附加滑点 {r['slippage_bps']:g} bps；平仓权益；资金费未计入。", "", result["draft"]["summary"], "", "## 可核验指标", "", "| 指标 | 数值 | 证据 |", "|---|---:|---|"]
    for claim in result["draft"]["claims"]:
        lines.append(f"| {METRIC_INFO[claim['metric']][0]} | {format_metric(claim['metric'], claim['value'])} | {claim['evidence_id']} → trades.csv / fills.csv |")
    lines += ["", "## 研究发现", ""] + ["- " + f for f in result["draft"]["findings"]]
    lines += ["", "## 成本比较", "", "固定成交与仓位路径，在每笔交易平仓时追加成本；包含全部进出场及加仓名义金额。", "", "| 单边手续费 bps | 累计收益 | 已实现回撤 | 额外成本 USDT |", "|---:|---:|---:|---:|"]
    for s in result["costs"]:
        v = s["metrics"]
        lines.append(f"| {s['fee_bps']:g} | {v['total_return']:.2%} | {v['max_drawdown']:.2%} | {v['added_fee_usdt']:,.2f} |")
    lines += ["", "## 数据与计算口径", "", f"代码版本：`{b['calc_version']}`；数据集：`{result['dataset']['dataset_id']}`。", "CAGR 沿用原生有效回测区间的整数日数，365 日年化；Sharpe 由 UTC 每日账户收益计算，标准差使用 ddof=1。子区间起始权益承接原账户，按平仓时点选择交易。", "成本敏感性不重新执行交易信号或仓位，不能解释为含延迟和市场冲击的重新回测。", ""]
    lines += ["- " + x for x in result["market"]["coverage"]["warnings"]]
    lines += ["", "## 独立复核", "", f"复核通过：{result['reviews'][-1]['passed']}；指标 {result['reviews'][-1]['checked_claims']} 项；成本情景 {result['reviews'][-1]['cost_scenarios_verified']} 组；纠错重跑：{result['repaired']}。", "", "## 证据索引", "", "| 编号 | 来源 | 定位 |", "|---|---|---|"]
    lines += [f"| {e['id']} | {e['title']} | {e['source']} |" for e in result["evidence"]]
    lines += ["| CALC-BASE | 账户指标计算 | result.json → base；trace.jsonl → calculate_metrics |", "| CALC-COST | 成交成本情景 | result.json → costs；trace.jsonl → compare_costs |", "| E-MARKET | OKX 历史行情附件 | market_daily.csv；manifest.json → market_sources |", "", "所有公开演示轨迹均保留生成时间与运行模式；离线报告由确定性模板组织，模型模式由 LLM 生成定性分析并经过同一复核门禁。"]
    return "\n".join(lines)


def render_html(result: dict) -> str:
    esc = lambda value: html.escape(str(value))
    r, b = result["request"], result["base"]
    metrics = b["metrics"]
    cards = "".join(f'<div class="card"><small>{esc(METRIC_INFO[k][0])}</small><strong>{esc(format_metric(k, metrics[k]))}</strong><span>CALC-BASE · Python 核验</span></div>' for k in ["trade_count", "cagr", "max_drawdown", "daily_sharpe"])
    rows = "".join(f"<tr><td>{esc(METRIC_INFO[c['metric']][0])}</td><td>{esc(format_metric(c['metric'], c['value']))}</td><td>{esc(c['evidence_id'])}</td></tr>" for c in result["draft"]["claims"])
    costs = "".join(f"<tr><td>{s['fee_bps']:g} bps</td><td>{s['metrics']['total_return']:.2%}</td><td>{s['metrics']['max_drawdown']:.2%}</td><td>{s['metrics']['added_fee_usdt']:,.2f}</td></tr>" for s in result["costs"])
    evidence = "".join(f'<tr><td>{esc(e["id"])}</td><td>{esc(e["title"])}</td><td>{esc(e["source"])}</td><td><code>{esc(e["source_hash"][:16])}</code></td></tr>' for e in result["evidence"])
    findings = "".join(f"<li>{esc(x)}</li>" for x in result["draft"]["findings"])
    warnings = "".join(f"<li>{esc(x)}</li>" for x in result["market"]["coverage"]["warnings"])
    plot = equity_figure(result, 460).to_html(full_html=False, include_plotlyjs=True, config={"displayModeBar": False})
    cost_plot = cost_figure(result).to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>金融研究报告 · {esc(result['run_id'])}</title>
<style>body{{margin:0;background:#f2f5f7;color:#172b3a;font:15px/1.8 'Segoe UI','Microsoft YaHei',sans-serif}}main{{max-width:1160px;margin:40px auto;background:white;padding:48px;border-radius:18px}}h1{{font-size:34px;letter-spacing:-1px;line-height:1.4}}h2{{font-size:21px;margin-top:36px}}.eyebrow{{font-size:12px;letter-spacing:3px;color:#087f75;font-weight:700}}.muted,small{{color:#687987}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}.card{{background:#f5f8f8;border:1px solid #dfebe9;border-radius:12px;padding:20px}}.card strong{{display:block;font-size:29px;color:#087f75}}.card span{{font-size:11px;color:#71838e}}table{{width:100%;border-collapse:collapse;font-size:13px;overflow-wrap:anywhere}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #e5eaed}}th{{background:#f6f8f9}}.summary{{border-left:4px solid #087f75;padding:8px 24px;margin:24px 0;background:#f2f8f7}}code{{font-size:11px}}@media(max-width:700px){{main{{margin:0;padding:20px}}.grid{{grid-template-columns:repeat(2,1fr)}}}}@media print{{body{{background:white}}main{{margin:0;padding:12px}}h2,table{{break-inside:avoid}}}}</style>
<main><div class="eyebrow">SARKAZ / QUANTITATIVE RESEARCH</div><h1>Sarkaz V3F<br>绩效与成本研究</h1><p>{esc(r['question'])}</p><p class="muted">{esc(result['execution_label'])} · 记录于 {esc(result['recorded_at_utc'])}<br>资产 {esc(r['asset'])} · [{esc(b['scope']['start'])}, {esc(b['scope']['end_exclusive'])}) UTC<br>单边 {r['fee_bps']:g} bps · 滑点 {r['slippage_bps']:g} bps · 资金费未计 · 平仓权益</p>
<div class="grid">{cards}</div><div class="summary">{esc(result['draft']['summary'])}</div><h2>账户权益与已实现回撤</h2>{plot}<h2>研究发现</h2><ul>{findings}</ul><h2>数值与证据绑定</h2><table><tr><th>指标</th><th>结果</th><th>证据编号</th></tr>{rows}</table><h2>成本压力测试</h2><p class="muted">固定成交路径，按进出场及加仓名义金额追加费用；各笔费用在平仓时入账。</p>{cost_plot}<table><tr><th>单边手续费</th><th>累计收益</th><th>已实现回撤</th><th>额外成本 USDT</th></tr>{costs}</table>
<h2>独立复核与样本口径</h2><p>已通过 {result['reviews'][-1]['checked_claims']} 项指标核验、{result['reviews'][-1]['cost_scenarios_verified']} 组成本复算。纠错执行：{'已触发并通过复核' if result['repaired'] else '无需修正'}。</p><p>CAGR 沿用原生有效回测区间的整数日数；Sharpe 使用 UTC 每日账户收益与样本标准差。子区间承接原账户起始权益。成本情景保留原成交路径与仓位。最大回撤取平仓权益，未覆盖持仓浮亏。</p><ul>{warnings}</ul><p class="muted">计算版本 {esc(b['calc_version'])} · 数据集 {esc(result['dataset']['dataset_id'])}<br>原回测 ZIP SHA-256：<code>{esc(result['dataset']['original_archive']['sha256'])}</code></p>
<h2>来源索引</h2><table><tr><th>编号</th><th>证据</th><th>定位</th><th>摘要/来源哈希</th></tr>{evidence}</table><p class="muted">CALC-BASE → result.json / base；CALC-COST → result.json / costs；E-MARKET → market_daily.csv。完整工具输入输出见同目录 trace.jsonl。</p><p class="muted">运行编号 {esc(result['run_id'])} · Prompt {esc(result['prompt']['version'])}</p></main></html>'''

