import type { ConnectedDeviceCategory, RoomDeviceTargets } from "@/types/roomos"

function categoriesFromScene(appliedScene: Partial<RoomDeviceTargets>): ConnectedDeviceCategory[] {
  const cats: ConnectedDeviceCategory[] = []
  if (appliedScene.brightness != null) cats.push("lights")
  if (appliedScene.fanOn != null) cats.push("smartPlugs")
  if (appliedScene.temperatureF != null) cats.push("thermostats")
  return cats
}

export function formatAppliedSceneSummary(
  appliedScene: Partial<RoomDeviceTargets>,
  connectedCategories: ConnectedDeviceCategory[] = [],
): string {
  const categories = connectedCategories.length
    ? connectedCategories
    : categoriesFromScene(appliedScene)

  if (!categories.length) {
    return "No devices connected"
  }

  const parts: string[] = []
  if (categories.includes("lights") && appliedScene.brightness != null) {
    parts.push(`Lights ${appliedScene.brightness}%`)
  }
  if (categories.includes("smartPlugs") && appliedScene.fanOn != null) {
    parts.push(appliedScene.fanOn ? "Fan on" : "Off")
  }
  if (categories.includes("thermostats") && appliedScene.temperatureF != null) {
    parts.push(`${appliedScene.temperatureF}°F`)
  }

  return parts.length ? parts.join(" · ") : "No devices connected"
}
