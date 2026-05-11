import { Link, Route, Routes } from "react-router-dom"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"

function Shell() {
  return (
    <div className="bg-background text-foreground min-h-svh">
      <div className="from-primary/15 via-background to-background pointer-events-none fixed inset-0 bg-gradient-to-b" />
      <div className="relative mx-auto flex min-h-svh max-w-3xl flex-col gap-8 px-6 py-16">
        <header className="space-y-2">
          <Badge variant="secondary" className="font-medium">
            Stack ready
          </Badge>
          <h1 className="text-foreground font-heading text-4xl font-semibold tracking-tight">
            HAVEN
          </h1>
          <p className="text-muted-foreground max-w-xl text-pretty text-base leading-relaxed">
            Frontend tooling is wired: Tailwind v4, shadcn (Radix Nova / Geist),
            TanStack Query, React Router, Framer Motion, and Zod. Replace this
            placeholder when you start the real UI.
          </p>
        </header>

        <Card className="border-border/80 shadow-sm">
          <CardHeader>
            <CardTitle>Sanity check</CardTitle>
            <CardDescription>
              If you see styled components and motion-ready tokens, the design
              system is working.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Example confidence</span>
                <span className="font-medium tabular-nums">72%</span>
              </div>
              <Progress value={72} />
            </div>
            <div className="flex flex-wrap gap-3">
              <Button asChild>
                <Link to="/other">Router link</Link>
              </Button>
              <Button variant="outline" type="button">
                Outline
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function Other() {
  return (
    <div className="bg-background text-foreground flex min-h-svh flex-col items-center justify-center gap-4 p-6">
      <p className="text-muted-foreground text-sm">Router is active.</p>
      <Button asChild variant="ghost">
        <Link to="/">Back home</Link>
      </Button>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Shell />} />
      <Route path="/other" element={<Other />} />
    </Routes>
  )
}
