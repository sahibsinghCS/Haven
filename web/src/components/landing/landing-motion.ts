/**
 * Shared motion language for the Haven marketing landing page.
 * Keep easing and viewport defaults consistent; vary per-section props only.
 */

import type { Variants } from "framer-motion"

/** Primary easing: confident, premium deceleration */
export const landingEase = {
  lux: [0.22, 1, 0.36, 1] as const,
  /** Slower, calmer: trust / privacy moments */
  grounded: [0.33, 1, 0.25, 1] as const,
  /** Hero / CTA: slightly more cinematic without bounce */
  velvet: [0.16, 1, 0.22, 1] as const,
}

/** Viewport presets for whileInView: once-only reveals */
export const landingViewport = {
  section: { once: true as const, margin: "-11% 0px -9% 0px" as const },
  headline: { once: true as const, margin: "-14% 0px -10% 0px" as const },
  /** Tighter trigger: narrative pipeline steps */
  pipelineStep: { once: true as const, margin: "-6% 0px -8% 0px" as const, amount: 0.35 as const },
  /** Calm blocks: privacy, assurance */
  assured: { once: true as const, margin: "-10% 0px -8% 0px" as const, amount: 0.28 as const },
  /** Product tiles: tactile previews */
  tactile: { once: true as const, margin: "-7% 0px -6% 0px" as const, amount: 0.3 as const },
  /** Strong finish */
  finale: { once: true as const, margin: "-12% 0px -18% 0px" as const, amount: 0.4 as const },
  card: { once: true as const, margin: "-8% 0px -6% 0px" as const, amount: 0.22 as const },
  cardDeep: { once: true as const, margin: "-5% 0px -5% 0px" as const, amount: 0.35 as const },
}

export const landingDuration = {
  micro: 0.42,
  standard: 0.58,
  slow: 0.72,
  hero: 0.88,
  spine: 1.05,
  cta: 0.95,
}

/**
 * Parent variant: stagger children for editorial reveals.
 */
export function landingStaggerParent(
  reduceMotion: boolean | null,
  staggerChildren = 0.075,
  delayChildren = 0.05,
): Variants {
  if (reduceMotion) {
    return {
      hidden: {},
      show: { transition: { staggerChildren: 0, delayChildren: 0 } },
    }
  }
  return {
    hidden: {},
    show: {
      transition: { staggerChildren, delayChildren },
    },
  }
}

/**
 * Child fade-up: default marketing reveal.
 */
export function landingFadeUp(
  reduceMotion: boolean | null,
  opts: {
    y?: number
    duration?: number
    ease?: readonly [number, number, number, number]
  } = {},
): Variants {
  const y = opts.y ?? 16
  const duration = opts.duration ?? landingDuration.standard
  const ease = opts.ease ?? landingEase.lux
  if (reduceMotion) {
    return {
      hidden: { opacity: 1, y: 0 },
      show: { opacity: 1, y: 0, transition: { duration: 0 } },
    }
  }
  return {
    hidden: { opacity: 0, y },
    show: { opacity: 1, y: 0, transition: { duration, ease } },
  }
}

/** Smaller travel + grounded ease: privacy, trust copy */
export function landingFadeGrounded(
  reduceMotion: boolean | null,
  opts: { y?: number; duration?: number } = {},
): Variants {
  return landingFadeUp(reduceMotion, {
    y: opts.y ?? 10,
    duration: opts.duration ?? landingDuration.slow,
    ease: landingEase.grounded,
  })
}

/** Opacity + scale only: pairs with parent `transform` (e.g. hero parallax). */
export function landingFadeScale(
  reduceMotion: boolean | null,
  opts: { scale?: number; duration?: number } = {},
): Variants {
  const scaleFrom = opts.scale ?? 0.982
  const duration = opts.duration ?? landingDuration.hero
  if (reduceMotion) {
    return {
      hidden: { opacity: 1, scale: 1 },
      show: { opacity: 1, scale: 1, transition: { duration: 0 } },
    }
  }
  return {
    hidden: { opacity: 0, scale: scaleFrom },
    show: {
      opacity: 1,
      scale: 1,
      transition: { duration, ease: landingEase.velvet },
    },
  }
}

/** Depth reveal: cards, floating panels (opacity + y + optional scale). */
export function landingFadeLift(
  reduceMotion: boolean | null,
  opts: { y?: number; scale?: number; duration?: number } = {},
): Variants {
  const y = opts.y ?? 28
  const scaleFrom = opts.scale ?? 0.988
  const duration = opts.duration ?? landingDuration.hero
  if (reduceMotion) {
    return {
      hidden: { opacity: 1, y: 0, scale: 1 },
      show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0 } },
    }
  }
  return {
    hidden: { opacity: 0, y, scale: scaleFrom },
    show: {
      opacity: 1,
      y: 0,
      scale: 1,
      transition: { duration, ease: landingEase.velvet },
    },
  }
}
