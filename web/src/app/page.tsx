import type { Metadata } from "next"

import { LandingPage } from "@/components/landing/landing-page"

export const metadata: Metadata = {
  description:
    "Haven reads context locally, surfaces calibrated confidence, and aligns light, airflow, and warmth, then refines baselines from how you adjust.",
  openGraph: {
    title: "Haven",
    description:
      "Local-first room intelligence: coherent scenes, legible confidence, environments that improve quietly from feedback.",
  },
}

export default function Home() {
  return <LandingPage />
}
