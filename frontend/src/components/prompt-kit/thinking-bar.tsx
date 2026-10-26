"use client"

import { TextShimmer } from "@/components/prompt-kit/text-shimmer"
import { cn } from "@/lib/utils"
import { Square } from "lucide-react"

type ThinkingBarProps = {
  className?: string
  text?: string
  onStop?: () => void
  stopLabel?: string
  onClick?: () => void
}

export function ThinkingBar({
  className,
  text = "Connecting to ATS boards...",
  onStop,
  stopLabel = "Stop",
  onClick,
}: ThinkingBarProps) {
  return (
    <div className={cn("flex w-full items-center justify-between text-xs py-1.5 px-3 border border-[var(--border)] bg-[var(--surface)] rounded-none!", className)}>
      {onClick ? (
        <button
          type="button"
          onClick={onClick}
          className="flex items-center gap-2 transition-opacity hover:opacity-80 text-left cursor-pointer"
        >
          <span className="w-2 h-2 bg-[var(--accent)] animate-pulse rounded-none! shrink-0" />
          <TextShimmer className="font-mono text-xs text-[var(--ink)]">{text}</TextShimmer>
        </button>
      ) : (
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 bg-[var(--accent)] animate-pulse rounded-none! shrink-0" />
          <TextShimmer className="cursor-default font-mono text-xs text-[var(--ink)]">{text}</TextShimmer>
        </div>
      )}
      {onStop ? (
        <button
          onClick={onStop}
          type="button"
          className="flex items-center gap-1 text-[11px] font-mono text-[var(--ink-muted)] hover:text-[var(--ink)] border border-[var(--border)] px-2 py-0.5 rounded-none! hover:bg-[var(--surface-hover)] transition-colors"
        >
          <Square className="h-2.5 w-2.5 fill-current" />
          <span>{stopLabel}</span>
        </button>
      ) : null}
    </div>
  )
}
