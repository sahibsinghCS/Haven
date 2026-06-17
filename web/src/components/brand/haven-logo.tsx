import Image from "next/image"
import type { ComponentPropsWithoutRef } from "react"

import { cn } from "@/lib/utils"

const ASSETS = {
  mark: { src: "/brand/haven-mark.png", width: 161, height: 165, alt: "Haven" },
  lockup: { src: "/brand/haven-lockup.png", width: 315, height: 95, alt: "Haven" },
  "lockup-mono": { src: "/brand/haven-lockup-mono.png", width: 304, height: 175, alt: "Haven" },
} as const

const SIZE_CLASS = {
  xs: "h-5",
  sm: "h-6",
  md: "h-7",
  lg: "h-8",
  xl: "h-10",
  "2xl": "h-14",
  hero: "h-[clamp(3.5rem,8vw,5.5rem)]",
} as const

export type HavenLogoVariant = keyof typeof ASSETS
export type HavenLogoSize = keyof typeof SIZE_CLASS

type HavenLogoProps = {
  variant?: HavenLogoVariant
  size?: HavenLogoSize
  className?: string
  priority?: boolean
} & Omit<ComponentPropsWithoutRef<"span">, "children">

export function HavenLogo({
  variant = "lockup",
  size = "md",
  className,
  priority = false,
  ...props
}: HavenLogoProps) {
  const asset = ASSETS[variant]

  return (
    <span className={cn("inline-flex shrink-0 items-center", className)} {...props}>
      <Image
        src={asset.src}
        alt={asset.alt}
        width={asset.width}
        height={asset.height}
        className={cn("w-auto select-none", SIZE_CLASS[size])}
        priority={priority}
        draggable={false}
      />
    </span>
  )
}

type HavenLogoBadgeProps = HavenLogoProps & {
  badgeClassName?: string
  /** Cream lockup on dark tile (default) or mono lockup on light pearl */
  tone?: "dark" | "light"
}

export function HavenLogoBadge({
  variant,
  size = "md",
  tone = "dark",
  className,
  badgeClassName,
  priority = false,
  ...props
}: HavenLogoBadgeProps) {
  const resolvedVariant = variant ?? (tone === "light" ? "lockup-mono" : "lockup")
  const resolvedSize = resolvedVariant === "mark" ? size : size === "xs" ? "sm" : size

  return (
    <span
      className={cn(
        "group/logo relative inline-flex items-center justify-center ring-1 transition-[box-shadow,transform] duration-200 ease-out",
        resolvedVariant === "mark" ? "overflow-visible rounded-[0.7rem]" : "overflow-hidden rounded-[0.7rem] px-2.5 py-1",
        tone === "dark"
          ? "bg-[linear-gradient(152deg,#242220_0%,#121110_48%,#0a0908_100%)] shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_10px_22px_-12px_rgba(0,0,0,0.45)] ring-white/14"
          : "bg-[color:var(--haven-surface,#fffefb)] shadow-[var(--haven-shadow-card,0_10px_30px_-12px_rgba(18,17,15,0.12))] ring-[color:var(--haven-line-strong,rgba(18,17,15,0.08))]",
        badgeClassName,
        className,
      )}
      {...props}
    >
      <span
        className={cn(
          "pointer-events-none absolute inset-[1px] rounded-[0.6rem] bg-gradient-to-br to-transparent opacity-80",
          tone === "dark" ? "from-white/10" : "from-white/70",
        )}
        aria-hidden
      />
      <HavenLogo variant={resolvedVariant} size={resolvedSize} priority={priority} className="relative z-[1]" />
    </span>
  )
}
