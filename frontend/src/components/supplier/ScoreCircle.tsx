"use client";

/** 评分圆环(SVG)。score 为 null 时显示灰色空环 + "评分中"。
 * 配色:≥80 绿 / ≥60 橙 / <60 红。
 */
export function ScoreCircle({ score }: { score: number | null }) {
  const size = 56;
  const stroke = 5;
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;

  if (score === null) {
    return (
      <div
        className="flex shrink-0 items-center justify-center rounded-full border-[5px] border-slate-100 text-[10px] text-slate-400"
        style={{ width: size, height: size }}
      >
        评分中
      </div>
    );
  }

  const pct = Math.max(0, Math.min(100, score)) / 100;
  const color = score >= 80 ? "#22c55e" : score >= 60 ? "#f97316" : "#ef4444";
  const dash = circ * pct;

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#f1f5f9" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ - dash}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-none">
        <span className="text-sm font-bold text-slate-900">{score}</span>
        <span className="text-[9px] text-slate-400">分</span>
      </div>
    </div>
  );
}
