"use client"

import { useState } from "react"
import { Eye, EyeOff } from "lucide-react"

import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { authInputClassName } from "@/components/auth/auth-form-field"
import { cn } from "@/lib/utils"

export function PasswordField({
  id,
  name,
  autoComplete,
  placeholder,
  showStrengthHint,
  defaultValue,
}: {
  id: string
  name: string
  autoComplete?: string
  placeholder?: string
  showStrengthHint?: boolean
  defaultValue?: string
}) {
  const [visible, setVisible] = useState(false)

  return (
    <div className="space-y-2">
      <div className="relative">
        <Input
          id={id}
          name={name}
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          placeholder={placeholder}
          defaultValue={defaultValue}
          minLength={6}
          required
          className={cn(authInputClassName(), "pr-11")}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="absolute top-1/2 right-1 size-9 -translate-y-1/2 text-[color:var(--haven-muted)] hover:bg-stone-900/[0.04]"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
        >
          {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
        </Button>
      </div>
      {showStrengthHint ? (
        <p className="text-[12px] text-[color:var(--haven-muted)]">At least 6 characters.</p>
      ) : null}
    </div>
  )
}
