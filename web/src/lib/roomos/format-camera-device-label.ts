/**
 * Strip marketing suffixes some virtual webcam drivers append to the device name
 * (e.g. "DroidCam Source 3 — use droidcam.app").
 */
export function formatCameraDeviceLabel(label: string): string {
  let s = label.trim()
  s = s.replace(/\s*[-–—|]\s*use\s+droidcam\.app\s*/gi, "")
  s = s.replace(/\s*use\s+droidcam\.app\s*/gi, "")
  s = s.replace(/\s*\(?\s*droidcam\.app\s*\)?\s*/gi, "")
  s = s.replace(/\s*https?:\/\/(?:www\.)?droidcam[^\s]*\s*/gi, " ")
  s = s.replace(/\s*[-–—|]\s*dev47apps\.com[^\s]*\s*/gi, "")
  s = s.replace(/\s+/g, " ").trim()
  return s.length > 0 ? s : "Camera"
}
