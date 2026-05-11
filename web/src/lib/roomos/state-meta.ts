import type { RoomStateId } from "@/types/roomos"

export const ROOM_STATE_LABEL: Record<RoomStateId, string> = {
  sleep: "Sleep",
  gaming: "Gaming",
  work: "Work / Studying",
  relaxing: "Relaxing",
  away: "Away",
}

/** Tailwind-friendly accent tokens for UI glow + charts (not device hex). */
export const ROOM_STATE_ACCENT: Record<
  RoomStateId,
  {
    /** Top wash for dashboard backdrop: kept mostly neutral; state tint is subtle */
    glow: string
    /** Full-bleed mesh behind the simulated camera: graphite base + controlled state hue */
    heroMesh: string
    bar: string
    ring: string
  }
> = {
  sleep: {
    glow: "from-zinc-800/42 via-zinc-950/35 to-transparent",
    heroMesh: "from-zinc-900 via-indigo-950/52 to-zinc-950",
    bar: "bg-indigo-400/60",
    ring: "ring-indigo-400/32",
  },
  gaming: {
    glow: "from-zinc-800/40 via-zinc-950/32 to-transparent",
    heroMesh: "from-zinc-900 via-violet-950/38 to-zinc-950",
    bar: "bg-violet-400/58",
    ring: "ring-violet-400/34",
  },
  work: {
    glow: "from-zinc-800/38 via-zinc-950/30 to-transparent",
    heroMesh: "from-zinc-900 via-sky-950/42 to-zinc-950",
    bar: "bg-cyan-400/58",
    ring: "ring-cyan-400/32",
  },
  relaxing: {
    glow: "from-zinc-800/36 via-zinc-950/28 to-transparent",
    heroMesh: "from-zinc-900 via-teal-950/40 to-zinc-950",
    bar: "bg-teal-400/55",
    ring: "ring-teal-400/30",
  },
  away: {
    glow: "from-zinc-800/34 via-zinc-950/28 to-transparent",
    heroMesh: "from-zinc-800 via-zinc-900 to-[#0a0a0b]",
    bar: "bg-zinc-400/50",
    ring: "ring-zinc-400/28",
  },
}

/** Marketing (light): distinctive washes + accents for landing state tiles */
export const ROOM_STATE_LANDING_SKIN: Record<
  RoomStateId,
  {
    wash: string
    bar: string
    tag: string
    glow: string
  }
> = {
  sleep: {
    wash: "from-indigo-50 via-violet-50/70 to-[#f6f3ec]",
    bar: "bg-indigo-500/70",
    tag: "bg-indigo-500/[0.12] text-indigo-950 ring-indigo-500/15",
    glow: "bg-indigo-400/25",
  },
  gaming: {
    wash: "from-violet-50 via-fuchsia-50/60 to-[#f6f3ec]",
    bar: "bg-violet-500/68",
    tag: "bg-violet-500/[0.12] text-violet-950 ring-violet-500/15",
    glow: "bg-violet-400/22",
  },
  work: {
    wash: "from-sky-50 via-cyan-50/55 to-[#f6f3ec]",
    bar: "bg-sky-600/65",
    tag: "bg-sky-500/[0.12] text-sky-950 ring-sky-500/15",
    glow: "bg-sky-400/22",
  },
  relaxing: {
    wash: "from-teal-50 via-emerald-50/50 to-[#f6f3ec]",
    bar: "bg-teal-600/62",
    tag: "bg-teal-500/[0.12] text-teal-950 ring-teal-500/14",
    glow: "bg-teal-400/20",
  },
  away: {
    wash: "from-stone-200/80 via-stone-100 to-[#f2efe8]",
    bar: "bg-stone-500/55",
    tag: "bg-stone-500/[0.12] text-stone-900 ring-stone-500/15",
    glow: "bg-stone-400/18",
  },
}

/** Landing: how each state feels in the environment (light / air / thermal). */
export const ROOM_STATE_LANDING_ATMOSPHERE: Record<
  RoomStateId,
  {
    tagline: string
    light: string
    air: string
    thermal: string
  }
> = {
  sleep: {
    tagline: "Rest-first posture: depth without glare.",
    light: "Low, moonlit wash; contrast where you need it.",
    air: "Near-still by default; movement only when you want it.",
    thermal: "Biased cool for easier drift toward sleep-friendly temps.",
  },
  gaming: {
    tagline: "Contrast for play: energy without spectacle.",
    light: "Screen-safe brightness; no strobing gimmicks.",
    air: "Fresh circulation when sessions stretch long.",
    thermal: "Held steady so the room stays out of the way.",
  },
  work: {
    tagline: "Even field for deep focus.",
    light: "Flat, gentle shadows, easy on long reads.",
    air: "Quiet airflow you stop noticing.",
    thermal: "Locked in with fewer thermal interruptions.",
  },
  relaxing: {
    tagline: "Recovery mode: warm, slow, wide.",
    light: "Amber-biased gradients with soft edges.",
    air: "Wide, slow movement and tactile calm.",
    thermal: "Open and cozy without going humid.",
  },
  away: {
    tagline: "Absent, but not unmanaged.",
    light: "Minimal baseline; presence without drama.",
    air: "Light-touch circulation on a sensible schedule.",
    thermal: "Lean targets with comfort waiting when you return.",
  },
}
