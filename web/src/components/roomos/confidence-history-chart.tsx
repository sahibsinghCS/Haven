"use client"

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import type { LiveInferenceSnapshot } from "@/types/roomos"

const stroke = {
  sleep: "#818cf8",
  gaming: "#c4b5fd",
  work: "#22d3ee",
  relaxing: "#2dd4bf",
  away: "#a1a1aa",
} as const

export function ConfidenceHistoryChart({
  history,
}: {
  history: LiveInferenceSnapshot["confidenceHistory"]
}) {
  const data = history.map((row) => ({
    ...row,
    label: new Date(row.t).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
  }))

  return (
    <div className="border-white/8 bg-white/[0.03] h-56 w-full rounded-2xl border p-3 shadow-inner backdrop-blur-md sm:h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
          <XAxis
            dataKey="label"
            tick={{ fill: "#a1a1aa", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            width={36}
            domain={[0, 1]}
            tickFormatter={(v) => `${Math.round(Number(v) * 100)}%`}
            tick={{ fill: "#a1a1aa", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "rgba(9,9,11,0.92)",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 12,
              color: "#e4e4e7",
              fontSize: 12,
            }}
            formatter={(value, name) => {
              const n = typeof value === "number" ? value : Number(value)
              const safe = Number.isFinite(n) ? n : 0
              return [`${Math.round(safe * 100)}%`, String(name)]
            }}
          />
          <Line type="monotone" dataKey="sleep" name="Sleep" stroke={stroke.sleep} dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="gaming" name="Gaming" stroke={stroke.gaming} dot={false} strokeWidth={2} />
          <Line type="monotone" dataKey="work" name="Work" stroke={stroke.work} dot={false} strokeWidth={2} />
          <Line
            type="monotone"
            dataKey="relaxing"
            name="Relaxing"
            stroke={stroke.relaxing}
            dot={false}
            strokeWidth={2}
          />
          <Line type="monotone" dataKey="away" name="Away" stroke={stroke.away} dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
