"use client"

import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react"
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useSpring,
  type Transition,
} from "framer-motion"

import { cn } from "@/lib/utils"

type SplitTextProps = {
  text: string
  /** When true, animate immediately on mount (e.g. hero). When false, on view. */
  immediate?: boolean
  className?: string
  charClassName?: string
  /** Delay before stagger begins */
  delay?: number
  /** Delay between characters */
  stagger?: number
  /** Travel distance for each char */
  y?: number
  /** Optional perspective tilt: adds gentle 3D feel */
  tilt?: boolean
  /** Add a metallic gloss sweep behind the text */
  shimmer?: boolean
  /** Color of the shimmer band */
  shimmerColor?: string
  as?: "span" | "div"
  /**
   * Apply `.landing-gloss-text` on each character, not the wrapper.
   * A gloss wrapper with transparent fill makes children inherit invisible text.
   */
  glossChars?: boolean
}

/**
 * Editorial per-character reveal with optional shimmer pass.
 *
 * - Splits on word boundaries to preserve a11y (full text remains in DOM via aria-label).
 * - Each character lifts + tilts in on a velvet ease.
 * - Optional shimmer sweeps once across the line after reveal settles.
 */
export function SplitText({
  text,
  immediate = false,
  className,
  charClassName,
  delay = 0,
  stagger = 0.022,
  y = 22,
  tilt = true,
  shimmer = false,
  shimmerColor = "rgba(255,243,214,0.85)",
  as = "span",
  glossChars = false,
}: SplitTextProps) {
  const reduceMotion = useReducedMotion()
  const Component = as === "div" ? motion.div : motion.span
  const words = useMemo(() => text.split(/(\s+)/), [text])

  const baseTransition: Transition = reduceMotion
    ? { duration: 0 }
    : { duration: 0.78, ease: [0.16, 1, 0.22, 1] }

  const parentInit = reduceMotion
    ? false
    : { transition: { staggerChildren: stagger, delayChildren: delay } }

  /** Avoid `hidden` / `show`. Parent motion trees (e.g. hero h1) use the same keys and can steal variant context. */
  const rootVariants = {
    splitIdle: {},
    splitRun: { transition: parentInit ? parentInit.transition : {} },
  } as const

  const charVariants = {
    splitIdle: reduceMotion
      ? { opacity: 1, y: 0, rotateX: 0, filter: "blur(0px)" }
      : { opacity: 0, y, rotateX: tilt ? -28 : 0, filter: "blur(6px)" },
    splitRun: {
      opacity: 1,
      y: 0,
      rotateX: 0,
      filter: "blur(0px)",
      transition: baseTransition,
    },
  } as const

  let charIdx = 0

  return (
    <Component
      aria-label={text}
      className={cn(
        "relative inline-block whitespace-pre-wrap leading-[inherit] [perspective:1200px]",
        className,
      )}
      initial={reduceMotion ? false : "splitIdle"}
      {...(immediate
        ? { animate: "splitRun" }
        : { whileInView: "splitRun", viewport: { once: true, margin: "-12% 0px -8% 0px" } })}
      variants={rootVariants}
    >
      {words.map((word, wi) => {
        if (/^\s+$/.test(word)) {
          return (
            <span key={`s-${wi}`} aria-hidden>
              {word}
            </span>
          )
        }
        return (
          <span key={`w-${wi}`} className="inline-block whitespace-nowrap" aria-hidden>
            {Array.from(word).map((ch, ci) => {
              charIdx++
              return (
                <motion.span
                  key={`c-${wi}-${ci}`}
                  variants={charVariants}
                  className={cn(
                    "inline-block will-change-transform [transform-style:preserve-3d]",
                    glossChars && "landing-gloss-text",
                    charClassName,
                  )}
                  style={{ transformOrigin: "50% 100%" }}
                >
                  {ch}
                </motion.span>
              )
            })}
          </span>
        )
      })}

      {shimmer && !reduceMotion ? (
        <motion.span
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-clip-text text-transparent"
          style={{
            backgroundImage: `linear-gradient(100deg, transparent 0%, transparent 38%, ${shimmerColor} 50%, transparent 62%, transparent 100%)`,
            backgroundSize: "240% 100%",
            backgroundRepeat: "no-repeat",
            mixBlendMode: "screen",
          }}
          initial={{ backgroundPositionX: "120%", opacity: 0 }}
          {...(immediate
            ? {
                animate: { backgroundPositionX: ["120%", "-30%"], opacity: [0, 1, 0] },
              }
            : {
                whileInView: { backgroundPositionX: ["120%", "-30%"], opacity: [0, 1, 0] },
                viewport: { once: true, margin: "-12% 0px -8% 0px" },
              })}
          transition={{
            duration: 1.6,
            delay: delay + Math.max(0.45, charIdx * stagger * 0.7),
            ease: [0.22, 1, 0.36, 1],
            times: [0, 0.4, 1],
          }}
        >
          {text}
        </motion.span>
      ) : null}
    </Component>
  )
}

/**
 * Magnetic: pulls its child toward the cursor on hover.
 *
 * Wrap a Link or button. The wrapper itself does not render any chrome;
 * it spring-translates so the child appears to be pulled by the cursor.
 */
export function Magnetic({
  children,
  strength = 0.32,
  radius = 120,
  className,
  style,
}: {
  children: ReactNode
  /** 0 maps to no movement, 1 to 1:1 follow. Premium feel sits around 0.25 to 0.4 */
  strength?: number
  /** Px radius around the element where magnetism engages */
  radius?: number
  className?: string
  style?: CSSProperties
}) {
  const ref = useRef<HTMLSpanElement | null>(null)
  const reduceMotion = useReducedMotion()
  const x = useMotionValue(0)
  const y = useMotionValue(0)
  const sx = useSpring(x, { stiffness: 260, damping: 22, mass: 0.4 })
  const sy = useSpring(y, { stiffness: 260, damping: 22, mass: 0.4 })
  const [coarse, setCoarse] = useState(false)

  useEffect(() => {
    setCoarse(window.matchMedia("(pointer: coarse)").matches)
  }, [])

  useEffect(() => {
    if (reduceMotion || coarse) return
    const el = ref.current
    if (!el) return

    let raf = 0
    const onMove = (event: PointerEvent) => {
      const r = el.getBoundingClientRect()
      const cx = r.left + r.width / 2
      const cy = r.top + r.height / 2
      const dx = event.clientX - cx
      const dy = event.clientY - cy
      const dist = Math.hypot(dx, dy)
      if (dist > radius + Math.max(r.width, r.height) / 2) {
        if (raf) cancelAnimationFrame(raf)
        raf = requestAnimationFrame(() => {
          x.set(0)
          y.set(0)
        })
        return
      }
      if (raf) cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        x.set(dx * strength)
        y.set(dy * strength)
      })
    }
    const onLeave = () => {
      x.set(0)
      y.set(0)
    }

    window.addEventListener("pointermove", onMove, { passive: true })
    window.addEventListener("pointerdown", onLeave)
    return () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerdown", onLeave)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [strength, radius, x, y, reduceMotion, coarse])

  if (reduceMotion || coarse) {
    return (
      <span ref={ref} className={cn("inline-block", className)} style={style}>
        {children}
      </span>
    )
  }

  return (
    <motion.span
      ref={ref}
      className={cn("inline-block will-change-transform", className)}
      style={{ x: sx, y: sy, ...style }}
    >
      {children}
    </motion.span>
  )
}
