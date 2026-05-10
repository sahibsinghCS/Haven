"use client"

import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

const chartData = [
  { t: "Mon", score: 42 },
  { t: "Tue", score: 55 },
  { t: "Wed", score: 48 },
  { t: "Thu", score: 72 },
  { t: "Fri", score: 68 },
]

export default function RoomTrendChart() {
  return (
    <div className="h-56 w-full min-h-56 min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <XAxis dataKey="t" stroke="var(--muted-foreground)" />
          <YAxis stroke="var(--muted-foreground)" width={32} />
          <Tooltip
            contentStyle={{
              background: "var(--popover)",
              border: "1px solid var(--border)",
              borderRadius: "8px",
            }}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="var(--primary)"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
