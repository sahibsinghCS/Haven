"use client"

import { useCallback, useEffect, useRef, useState } from "react"

export type LiveRoomCameraStatus =
  | "idle"
  | "requesting"
  | "live"
  | "denied"
  | "unsupported"
  | "error"

function pickDroidCamDeviceId(devices: MediaDeviceInfo[]): string | undefined {
  const videoInputs = devices.filter((d) => d.kind === "videoinput")
  const byLabel = videoInputs.find((d) => /droidcam/i.test(d.label))
  return byLabel?.deviceId
}

export function useLiveRoomCamera(selectedDeviceId: string | null) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [openAttempt, setOpenAttempt] = useState(0)
  const [status, setStatus] = useState<LiveRoomCameraStatus>("idle")
  const [message, setMessage] = useState<string | null>(null)
  const [videoInputs, setVideoInputs] = useState<MediaDeviceInfo[]>([])
  const [activeDeviceId, setActiveDeviceId] = useState<string | undefined>(undefined)

  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("unsupported")
      setMessage("This browser does not support camera capture.")
      return
    }

    let cancelled = false

    async function run() {
      setStatus("requesting")
      setMessage(null)
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null

      try {
        let stream: MediaStream

        if (selectedDeviceId) {
          stream = await navigator.mediaDevices.getUserMedia({
            video: { deviceId: { exact: selectedDeviceId } },
          })
        } else {
          stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 1280 }, height: { ideal: 720 } },
          })
          const listed = (await navigator.mediaDevices.enumerateDevices()).filter(
            (d) => d.kind === "videoinput",
          )
          if (cancelled) {
            stream.getTracks().forEach((t) => t.stop())
            return
          }
          setVideoInputs(listed)

          const droidId = pickDroidCamDeviceId(listed)
          const currentId = stream.getVideoTracks()[0]?.getSettings().deviceId
          if (droidId && currentId && droidId !== currentId) {
            stream.getTracks().forEach((t) => t.stop())
            stream = await navigator.mediaDevices.getUserMedia({
              video: { deviceId: { exact: droidId } },
            })
          }
        }

        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }

        const listed = (await navigator.mediaDevices.enumerateDevices()).filter(
          (d) => d.kind === "videoinput",
        )
        setVideoInputs(listed)

        streamRef.current = stream
        const usedId = stream.getVideoTracks()[0]?.getSettings().deviceId
        setActiveDeviceId(usedId)

        const el = videoRef.current
        if (el) {
          el.srcObject = stream
          void el.play().catch(() => {})
        }
        setStatus("live")
      } catch (e) {
        if (cancelled) return
        const err = e as DOMException
        if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
          setStatus("denied")
          setMessage("Allow camera access for this site, then try again.")
        } else if (err.name === "NotFoundError") {
          setStatus("error")
          setMessage("No camera found. Connect your camera, then refresh.")
        } else if (err.name === "OverconstrainedError") {
          setStatus("error")
          setMessage("That camera is not available. Choose another device.")
        } else {
          setStatus("error")
          setMessage(err.message || "Could not start the camera.")
        }
      }
    }

    void run()

    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [selectedDeviceId, openAttempt])

  const retry = useCallback(() => {
    setOpenAttempt((n) => n + 1)
  }, [])

  return { videoRef, status, message, videoInputs, activeDeviceId, retry }
}
