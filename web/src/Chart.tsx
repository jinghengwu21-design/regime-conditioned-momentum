import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { LineChart, BarChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkAreaComponent,
} from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";

echarts.use([
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkAreaComponent,
  SVGRenderer,
]);
export const colors = {
  green: "#2d6b59",
  blue: "#7f92a7",
  red: "#ac6b5d",
  amber: "#a18147",
  text: "#849180",
  grid: "#e3e8de",
};
export function lineOption(
  dates: string[],
  series: {
    name: string;
    data: (number | null)[];
    color: string;
    area?: boolean;
    step?: boolean;
  }[],
  percent = false,
  log = false,
): EChartsCoreOption {
  return {
    animation: false,
    textStyle: {
      fontFamily: "Inter, Microsoft YaHei, sans-serif",
      color: colors.text,
      fontSize: 11,
    },
    grid: { left: 55, right: 20, top: 20, bottom: 32 },
    tooltip: {
      trigger: "axis",
      backgroundColor: "#ffffff",
      borderColor: "#ccd8c5",
      textStyle: { color: "#344432", fontSize: 12 },
      valueFormatter: (value: unknown) =>
        typeof value === "number"
          ? percent
            ? `${(value * 100).toFixed(2)}%`
            : value.toLocaleString("en-US", { maximumFractionDigits: 2 })
          : "—",
    },
    xAxis: {
      type: "category",
      data: dates,
      boundaryGap: false,
      axisLine: { lineStyle: { color: colors.grid } },
      axisTick: { show: false },
      axisLabel: {
        color: colors.text,
        hideOverlap: true,
        formatter: (v: string) => v.slice(0, 7),
      },
    },
    yAxis: {
      type: log ? "log" : "value",
      splitNumber: 4,
      scale: true,
      axisLabel: {
        color: colors.text,
        formatter: (v: number) =>
          percent
            ? `${(v * 100).toFixed(0)}%`
            : Math.abs(v) >= 1000
              ? `${(v / 1000).toFixed(0)}k`
              : `${v}`,
      },
      splitLine: { lineStyle: { color: colors.grid, type: "dashed" } },
    },
    series: series.map((s) => ({
      name: s.name,
      type: "line",
      data: s.data,
      showSymbol: false,
      connectNulls: false,
      step: s.step ? "end" : false,
      lineStyle: { width: 1.7, color: s.color },
      itemStyle: { color: s.color },
      areaStyle: s.area
        ? {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: s.color + "24" },
              { offset: 1, color: s.color + "00" },
            ]),
          }
        : undefined,
    })),
  };
}
export function Chart({
  option,
  height = 300,
  label,
}: {
  option: EChartsCoreOption;
  height?: number;
  label: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const chart = echarts.init(ref.current!, undefined, { renderer: "svg" });
    chart.setOption(option);
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current!);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [option]);
  return (
    <div
      ref={ref}
      style={{ height, width: "100%" }}
      role="img"
      aria-label={label}
    />
  );
}
