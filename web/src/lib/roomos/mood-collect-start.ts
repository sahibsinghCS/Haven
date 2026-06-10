/** Query params for starting mood collection on /live. */

export function moodCollectFromSearch(search: string): {
  moodId: string | null
  durationSec: number
} {
  try {
    const params = new URLSearchParams(search)
    const moodId = params.get("moodCollect")?.trim() || null
    const raw = params.get("duration")
    const durationSec = raw ? Math.min(3600, Math.max(10, Number(raw))) : 300
    return {
      moodId,
      durationSec: Number.isFinite(durationSec) ? durationSec : 300,
    }
  } catch {
    return { moodId: null, durationSec: 300 }
  }
}

export function buildLiveCollectUrl(moodId: string, durationSec: number): string {
  const params = new URLSearchParams({
    start: "1",
    moodCollect: moodId,
    duration: String(Math.round(durationSec)),
  })
  return `/live?${params.toString()}`
}

export function stripCollectQueryFromUrl(): void {
  if (typeof window === "undefined") return
  try {
    const url = new URL(window.location.href)
    if (!url.searchParams.has("moodCollect") && !url.searchParams.has("duration")) return
    url.searchParams.delete("moodCollect")
    url.searchParams.delete("duration")
    const next = `${url.pathname}${url.search}${url.hash}`
    window.history.replaceState({}, "", next)
  } catch {
    /* ignore */
  }
}
