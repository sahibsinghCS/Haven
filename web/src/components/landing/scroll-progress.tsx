"use client"

import { motion, useReducedMotion, useScroll, useSpring } from "framer-motion"

export function ScrollProgress() {
  const reduceMotion = useReducedMotion()
  const { scrollYProgress } = useScroll()
  const scaleX = useSpring(scrollYProgress, {
    stiffness: reduceMotion ? 1000 : 130,
    damping: reduceMotion ? 100 : 22,
    mass: 0.28,
  })

  return (
    <div className="pointer-events-none fixed left-0 top-0 z-[80] h-[3px] w-full">
      <motion.div
        aria-hidden
        className="absolute inset-0 origin-left bg-[linear-gradient(90deg,rgba(247,232,200,0.62)_0%,rgba(45,212,191,0.85)_52%,rgba(15,118,110,1)_100%)]"
        style={{ scaleX }}
      />
      <motion.div
        aria-hidden
        className="absolute inset-0 origin-left opacity-70 mix-blend-screen bg-[linear-gradient(90deg,transparent_0%,rgba(255,243,214,0.4)_38%,rgba(45,212,191,0.55)_72%,transparent_100%)] blur-[2px]"
        style={{ scaleX }}
      />
    </div>
  )
}
