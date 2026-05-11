"use client"

import dynamic from "next/dynamic"
import { zodResolver } from "@hookform/resolvers/zod"
import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Activity, Server } from "lucide-react"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { createRoomSocket } from "@/lib/realtime"
import { useRoomStore } from "@/stores/room-store"

const RoomTrendChart = dynamic(() => import("./room-trend-chart"), {
  ssr: false,
  loading: () => (
    <div className="bg-muted/30 text-muted-foreground flex h-56 items-center justify-center rounded-lg text-sm">
      Loading chart…
    </div>
  ),
})

const calibrationSchema = z.object({
  deviceLabel: z.string().min(2, "Use at least 2 characters"),
})

type CalibrationValues = z.infer<typeof calibrationSchema>

export function StackDemo() {
  const phase = useRoomStore((s) => s.phase)
  const lastMessage = useRoomStore((s) => s.lastMessage)
  const setPhase = useRoomStore((s) => s.setPhase)
  const touchEvent = useRoomStore((s) => s.touchEvent)

  const health = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const res = await fetch("/api/health", { cache: "no-store" })
      if (!res.ok) {
        throw new Error("Health check failed")
      }
      return (await res.json()) as { status: string }
    },
  })

  const form = useForm<CalibrationValues>({
    resolver: zodResolver(calibrationSchema),
    defaultValues: { deviceLabel: "" },
  })

  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_WS_URL
    if (!url) {
      setPhase("idle")
      return
    }

    setPhase("connecting")
    const socket = createRoomSocket(url, {
      onOpen: () => {
        setPhase("live")
        touchEvent("connected")
      },
      onClose: () => setPhase("idle"),
      onError: () => setPhase("error"),
      onMessage: (data) => touchEvent(JSON.stringify(data)),
    })

    return () => {
      socket.close()
    }
  }, [setPhase, touchEvent])

  return (
    <div className="relative flex flex-1 flex-col gap-10 px-6 py-14">
      <div className="from-primary/12 via-background to-background pointer-events-none fixed inset-0 bg-gradient-to-b" />
      <div className="relative mx-auto flex w-full max-w-4xl flex-col gap-8">
        <motion.header
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="space-y-3"
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="gap-1 font-medium">
              <Activity className="size-3.5" aria-hidden />
              Stack wired
            </Badge>
            <Badge variant="outline" className="font-mono text-xs">
              Zustand: {phase}
            </Badge>
          </div>
          <h1 className="text-foreground font-heading text-4xl font-semibold tracking-tight">
            Haven
          </h1>
          <p className="text-muted-foreground max-w-2xl text-pretty text-base leading-relaxed">
            Next.js, Tailwind, shadcn/ui, Zustand, TanStack Query, React Hook
            Form + Zod, Framer Motion, Recharts, Sonner, Lucide, and a
            reconnecting WebSocket client, ready for the real dashboard.
          </p>
        </motion.header>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="border-border/80 shadow-sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Server className="size-4" aria-hidden />
                TanStack Query
              </CardTitle>
              <CardDescription>
                Proxied <code className="text-xs">GET /api/health</code> against FastAPI
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {health.isLoading ? (
                <p className="text-muted-foreground text-sm">Checking API…</p>
              ) : health.isError ? (
                <p className="text-destructive text-sm">
                  API unreachable. Start the backend{" "}
                  <code className="font-mono text-xs">npm run dev:api</code>.
                </p>
              ) : (
                <p className="text-sm">
                  Status:{" "}
                  <span className="font-medium">{health.data?.status}</span>
                </p>
              )}
              <Progress value={health.isSuccess ? 100 : health.isLoading ? 40 : 15} />
            </CardContent>
          </Card>

          <Card className="border-border/80 shadow-sm">
            <CardHeader>
              <CardTitle>React Hook Form + Zod</CardTitle>
              <CardDescription>Calibration-style field (demo)</CardDescription>
            </CardHeader>
            <CardContent>
              <Form {...form}>
                <form
                  className="space-y-4"
                  onSubmit={form.handleSubmit((values) => {
                    toast.success(`Saved “${values.deviceLabel}” (demo)`)
                  })}
                >
                  <FormField
                    control={form.control}
                    name="deviceLabel"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Device label</FormLabel>
                        <FormControl>
                          <Input placeholder="Desk lamp" {...field} />
                        </FormControl>
                        <FormDescription>
                          Shown on the setup screen later.
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <Button type="submit">Save</Button>
                </form>
              </Form>
            </CardContent>
          </Card>

          <Card className="border-border/80 shadow-sm lg:col-span-2">
            <CardHeader>
              <CardTitle>Recharts</CardTitle>
              <CardDescription>Example trend (placeholder data)</CardDescription>
            </CardHeader>
            <CardContent>
              <RoomTrendChart />
            </CardContent>
          </Card>

          <Card className="border-border/80 shadow-sm lg:col-span-2">
            <CardHeader>
              <CardTitle>WebSocket + Zustand</CardTitle>
              <CardDescription>
                Set{" "}
                <code className="font-mono text-xs">NEXT_PUBLIC_WS_URL</code>{" "}
                to enable the live client (e.g.{" "}
                <code className="font-mono text-xs">ws://127.0.0.1:8000/ws</code>
                ).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p className="text-muted-foreground">
                Last event:{" "}
                <span className="text-foreground font-medium">
                  {lastMessage ?? "No message yet"}
                </span>
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
