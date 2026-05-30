"use client"

import { cn } from "@/lib/utils"
import { feedbackEvidenceFrameUrl } from "@/lib/roomos/api-client"

/** Thumbnails for the burst that live feedback would persist. */
export function FeedbackEvidenceStrip({
  frameCount,
  cacheKey,
  className,
  frameClassName,
}: {
  frameCount: number
  /** Bust browser cache when evidence updates (e.g. snapshot sequence). */
  cacheKey?: string
  className?: string
  frameClassName?: string
}) {
  const n = Math.max(0, Math.min(5, frameCount))
  if (n < 1) return null

  return (
    <div className={cn("flex gap-1 overflow-x-auto", className)}>
      {Array.from({ length: n }, (_, i) => i + 1).map((idx) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={idx}
          src={feedbackEvidenceFrameUrl(idx, cacheKey)}
          alt={`Burst frame ${idx}`}
          className={cn(
            "h-14 w-20 shrink-0 rounded-md border border-white/10 object-cover",
            frameClassName,
          )}
          loading="lazy"
        />
      ))}
    </div>
  )
}
