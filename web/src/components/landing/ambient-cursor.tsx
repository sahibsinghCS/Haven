"use client"

import { useEffect, useRef, useState } from "react"
import { motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring, useTransform } from "framer-motion"

function pointerInHeroBounds(clientX: number, clientY: number): boolean {
  const hero = document.getElementById("hero")
  if (!hero) return false
  const r = hero.getBoundingClientRect()
  return clientX >= r.left && clientX <= r.right && clientY >= r.top && clientY <= r.bottom
}

/**
 * Hero-only ambient cursor: dual element on the dark fold, nothing on light sections
 * (avoids multiply-blend smudges over cards and double-cursor with system pointer).
 */
export function AmbientCursor() {
  const reduceMotion = useReducedMotion()
  const [enabled, setEnabled] = useState(false)
  const [pressed, setPressed] = useState(false)
  const [hover, setHover] = useState<null | { x: number; y: number; w: number; h: number; radius: number }>(null)
  const [tone, setTone] = useState<"light" | "dark">("dark")
  const [visible, setVisible] = useState(true)
  const [inHero, setInHero] = useState(false)
  const lastPointer = useRef({ x: -1, y: -1 })

  const x = useMotionValue(-400)
  const y = useMotionValue(-400)

  const dotX = useSpring(x, { stiffness: 900, damping: 60, mass: 0.18 })
  const dotY = useSpring(y, { stiffness: 900, damping: 60, mass: 0.18 })

  const haloX = useSpring(x, { stiffness: 180, damping: 26, mass: 0.4 })
  const haloY = useSpring(y, { stiffness: 180, damping: 26, mass: 0.4 })

  const targetX = useMotionValue(0)
  const targetY = useMotionValue(0)
  const targetW = useMotionValue(0)
  const targetH = useMotionValue(0)
  const targetR = useMotionValue(999)
  const focusProgress = useMotionValue(0)

  const focusX = useSpring(targetX, { stiffness: 320, damping: 32, mass: 0.35 })
  const focusY = useSpring(targetY, { stiffness: 320, damping: 32, mass: 0.35 })
  const focusW = useSpring(targetW, { stiffness: 280, damping: 30, mass: 0.4 })
  const focusH = useSpring(targetH, { stiffness: 280, damping: 30, mass: 0.4 })
  const focusR = useSpring(targetR, { stiffness: 280, damping: 30, mass: 0.4 })
  const focusAmt = useSpring(focusProgress, { stiffness: 220, damping: 28, mass: 0.35 })

  const haloXMix = useTransform([haloX, focusX, focusAmt], (v) => {
    const [hx, fx, a] = v as [number, number, number]
    return hx * (1 - a) + fx * a
  })
  const haloYMix = useTransform([haloY, focusY, focusAmt], (v) => {
    const [hy, fy, a] = v as [number, number, number]
    return hy * (1 - a) + fy * a
  })
  const haloW = useTransform([focusW, focusAmt], (v) => {
    const [w, a] = v as [number, number]
    return 96 * (1 - a) + (w + 18) * a
  })
  const haloH = useTransform([focusH, focusAmt], (v) => {
    const [h, a] = v as [number, number]
    return 96 * (1 - a) + (h + 18) * a
  })
  const haloRadius = useTransform([focusR, focusAmt], (v) => {
    const [r, a] = v as [number, number]
    return 999 * (1 - a) + r * a
  })
  const haloRadiusStr = useMotionTemplate`${haloRadius}px`
  const haloWStr = useMotionTemplate`${haloW}px`
  const haloHStr = useMotionTemplate`${haloH}px`

  useEffect(() => {
    if (reduceMotion) return
    const media = window.matchMedia("(pointer: fine)")
    const update = () => setEnabled(media.matches)
    update()
    media.addEventListener("change", update)
    return () => media.removeEventListener("change", update)
  }, [reduceMotion])

  useEffect(() => {
    if (!enabled || reduceMotion) return

    const findTarget = (el: EventTarget | null): HTMLElement | null => {
      let node = el as HTMLElement | null
      while (node && node !== document.body) {
        if (
          node.matches?.(
            "a, button, [role='button'], [data-cursor='hover'], summary, label[for], input[type='submit']",
          )
        ) {
          return node
        }
        node = node.parentElement
      }
      return null
    }

    const detectTone = (clientX: number, clientY: number) => {
      const el = document.elementFromPoint(clientX, clientY) as HTMLElement | null
      if (!el) return
      let node: HTMLElement | null = el
      while (node && node !== document.body) {
        const bg = getComputedStyle(node).backgroundColor
        if (bg && bg !== "rgba(0, 0, 0, 0)") {
          const m = bg.match(/\d+(\.\d+)?/g)
          if (m && m.length >= 3) {
            const [r, g, b] = m.map(Number)
            const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
            setTone(luma < 90 ? "dark" : "light")
            return
          }
        }
        node = node.parentElement
      }
      setTone("dark")
    }

    const syncInHero = () => {
      const { x: px, y: py } = lastPointer.current
      if (px < 0 || py < 0) return
      setInHero(pointerInHeroBounds(px, py))
    }

    let lastTone = 0
    const onMove = (event: PointerEvent) => {
      lastPointer.current = { x: event.clientX, y: event.clientY }
      setInHero(pointerInHeroBounds(event.clientX, event.clientY))

      x.set(event.clientX)
      y.set(event.clientY)
      if (!visible) setVisible(true)

      const now = performance.now()
      if (now - lastTone > 90) {
        lastTone = now
        detectTone(event.clientX, event.clientY)
      }

      const target = findTarget(event.target)
      if (target) {
        const r = target.getBoundingClientRect()
        const cs = getComputedStyle(target)
        const radius = parseFloat(cs.borderRadius) || 14
        targetX.set(r.left + r.width / 2)
        targetY.set(r.top + r.height / 2)
        targetW.set(r.width)
        targetH.set(r.height)
        targetR.set(Math.min(radius, r.height / 2))
        focusProgress.set(1)
        setHover({ x: r.left, y: r.top, w: r.width, h: r.height, radius })
      } else {
        focusProgress.set(0)
        setHover(null)
      }
    }

    const onDown = () => setPressed(true)
    const onUp = () => setPressed(false)
    const onLeave = () => setVisible(false)
    const onEnter = () => setVisible(true)

    window.addEventListener("pointermove", onMove, { passive: true })
    window.addEventListener("pointerdown", onDown)
    window.addEventListener("pointerup", onUp)
    window.addEventListener("scroll", syncInHero, { passive: true })
    window.addEventListener("resize", syncInHero)
    document.addEventListener("pointerleave", onLeave)
    document.addEventListener("pointerenter", onEnter)
    return () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerdown", onDown)
      window.removeEventListener("pointerup", onUp)
      window.removeEventListener("scroll", syncInHero)
      window.removeEventListener("resize", syncInHero)
      document.removeEventListener("pointerleave", onLeave)
      document.removeEventListener("pointerenter", onEnter)
    }
  }, [enabled, reduceMotion, x, y, targetX, targetY, targetW, targetH, targetR, focusProgress, visible])

  if (!enabled || reduceMotion || !inHero) return null

  const isDark = tone === "dark"
  const showHalo = isDark
  const haloBg =
    "radial-gradient(circle, rgba(255,243,214,0.32) 0%, rgba(245,158,11,0.18) 38%, rgba(20,184,166,0.16) 64%, transparent 78%)"
  const haloBorder = "rgba(255,247,231,0.18)"
  const dotBg = isDark ? "#fbf3df" : "#0f766e"
  const opacityMul = visible ? 1 : 0

  return (
    <>
      {showHalo ? (
        <motion.div
          aria-hidden
          className="pointer-events-none fixed left-0 top-0 z-[60] hidden lg:block"
          style={{
            x: haloXMix,
            y: haloYMix,
            width: haloWStr,
            height: haloHStr,
            translateX: "-50%",
            translateY: "-50%",
            borderRadius: haloRadiusStr,
            opacity: opacityMul * (pressed ? 0.95 : 0.78),
            background: haloBg,
            boxShadow:
              "0 0 60px 6px rgba(255,225,170,0.10), inset 0 0 0 1px rgba(255,247,231,0.10)",
            border: `1px solid ${haloBorder}`,
            mixBlendMode: "screen",
            transition: "opacity 220ms ease, background 360ms ease, border-color 360ms ease",
            willChange: "transform, width, height, border-radius",
          }}
        />
      ) : null}

      <motion.div
        aria-hidden
        className="pointer-events-none fixed left-0 top-0 z-[61] hidden lg:block"
        style={{
          x: dotX,
          y: dotY,
          translateX: "-50%",
          translateY: "-50%",
          width: pressed ? 4 : hover ? 5 : 7,
          height: pressed ? 4 : hover ? 5 : 7,
          borderRadius: 999,
          background: dotBg,
          boxShadow: isDark
            ? "0 0 0 1px rgba(8,7,6,0.5), 0 0 10px rgba(251,243,223,0.55)"
            : "0 0 0 1px rgba(255,255,255,0.7), 0 0 10px rgba(15,118,110,0.45)",
          opacity: opacityMul,
          transition: "width 220ms ease, height 220ms ease, background 360ms ease, box-shadow 360ms ease",
          willChange: "transform",
        }}
      />
    </>
  )
}
