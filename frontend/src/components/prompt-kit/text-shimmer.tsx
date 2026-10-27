"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

export type TextShimmerProps = {
  as?: string
  duration?: number
  spread?: number
  children: React.ReactNode
} & React.HTMLAttributes<HTMLElement>

export function TextShimmer({
  as = "span",
  className,
  duration = 3,
  spread = 20,
  children,
  ...props
}: TextShimmerProps) {
  const dynamicSpread = Math.min(Math.max(spread, 5), 45)
  const Component = as as React.ElementType

  return (
    <Component
      className={cn(
        "bg-size-[200%_auto] bg-clip-text font-medium text-transparent",
        "animate-[shimmer_3s_infinite_linear]",
        className
      )}
      style={{
        backgroundImage: `linear-gradient(to right, var(--ink-muted, #5C5A53) ${50 - dynamicSpread}%, var(--ink, #181816) 50%, var(--ink-muted, #5C5A53) ${50 + dynamicSpread}%)`,
        animationDuration: `${duration}s`,
      }}
      {...props}
    >
      {children}
    </Component>
  )
}
