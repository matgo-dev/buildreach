"use client";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import type { DimensionOut } from "@/lib/api/credit";

/** 四维评分雷达图(PRD §8.1)。
 *
 * 把各维度得分归一化为百分比(score / max_score),雷达半径 0-100。
 * 配色按总分映射:全平台单色,不按维度分别上色(避免视觉混乱)。
 */
export function CreditRadarChart({
  dimensions,
  totalScore,
}: {
  dimensions: DimensionOut[];
  totalScore: number;
}) {
  const data = dimensions.map((d) => ({
    dim: `${d.name}\n${d.score}/${d.max_score}`,
    pct: d.max_score > 0 ? Math.round((d.score / d.max_score) * 100) : 0,
    score: d.score,
    max: d.max_score,
  }));

  const fill =
    totalScore >= 80
      ? "#22c55e"
      : totalScore >= 60
        ? "#eab308"
        : totalScore >= 40
          ? "#f97316"
          : "#ef4444";

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <RadarChart cx="50%" cy="50%" outerRadius="75%" data={data}>
          <PolarGrid stroke="#e2e8f0" />
          <PolarAngleAxis
            dataKey="dim"
            tick={{ fontSize: 11, fill: "#475569" }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: "#94a3b8" }}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            formatter={(value, name, item) => {
              const p = item?.payload as { score?: number; max?: number };
              if (p && typeof p.score === "number") {
                return [`${p.score} / ${p.max}`, "得分"];
              }
              return [String(value), String(name)];
            }}
          />
          <Radar
            name="得分占比"
            dataKey="pct"
            stroke={fill}
            fill={fill}
            fillOpacity={0.35}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
