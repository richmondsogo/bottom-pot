"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"
import {
  Check,
  ChevronDown,
  Loader2,
  Terminal,
  AlertCircle,
  Database,
} from "lucide-react"

export type ToolPart = {
  type: string
  state:
    | "input-streaming"
    | "input-available"
    | "output-available"
    | "output-error"
    | "cached"
  input?: Record<string, unknown>
  output?: Record<string, unknown>
  toolCallId?: string
  errorText?: string
  durationMs?: number
  resultCount?: number
  cached?: boolean
}

export type ToolProps = {
  toolPart: ToolPart
  defaultOpen?: boolean
  className?: string
}

export function Tool({ toolPart, defaultOpen = false, className }: ToolProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen)
  const { state, input, output, toolCallId, durationMs, resultCount, cached } = toolPart

  const getStateIcon = () => {
    if (cached || state === "cached") {
      return <Database className="h-3.5 w-3.5 text-[var(--accent)]" />
    }
    switch (state) {
      case "input-streaming":
        return <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--ink-muted)]" />
      case "output-available":
        return <Check className="h-3.5 w-3.5 text-[var(--accent)]" />
      case "output-error":
        return <AlertCircle className="h-3.5 w-3.5 text-red-600 dark:text-red-400" />
      default:
        return <Terminal className="h-3.5 w-3.5 text-[var(--ink-subtle)]" />
    }
  }

  const getStateBadge = () => {
    const baseClasses = "px-1.5 py-0.5 rounded-none! text-[11px] font-mono tracking-tight"
    if (cached || state === "cached") {
      return (
        <span className={cn(baseClasses, "border border-[var(--border)] bg-[var(--surface-hover)] text-[var(--accent)] font-medium")}>
          cached
        </span>
      )
    }
    switch (state) {
      case "input-streaming":
        return (
          <span className={cn(baseClasses, "border border-[var(--border)] bg-[var(--surface-subtle)] text-[var(--ink-muted)]")}>
            streaming...
          </span>
        )
      case "output-available":
        return (
          <span className={cn(baseClasses, "border border-[var(--border)] bg-[var(--surface-hover)] text-[var(--ink)]")}>
            {resultCount !== undefined ? `${resultCount} listings` : "completed"}
          </span>
        )
      case "output-error":
        return (
          <span className={cn(baseClasses, "border border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400")}>
            error
          </span>
        )
      default:
        return (
          <span className={cn(baseClasses, "border border-[var(--border)] bg-[var(--surface)] text-[var(--ink-subtle)]")}>
            pending
          </span>
        )
    }
  }

  const formatValue = (value: unknown): string => {
    if (value === null) return "null"
    if (value === undefined) return "undefined"
    if (typeof value === "string") return value
    if (typeof value === "object") {
      return JSON.stringify(value, null, 2)
    }
    return String(value)
  }

  return (
    <div
      className={cn(
        "rounded-none! border border-[var(--border)] bg-[var(--surface)] overflow-hidden transition-colors",
        className
      )}
    >
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="rounded-none! h-9 w-full justify-between px-3 py-1.5 font-normal hover:bg-[var(--surface-hover)] text-left"
          >
            <div className="flex items-center gap-2 truncate">
              {getStateIcon()}
              <span className="font-mono text-xs font-medium text-[var(--ink)] lowercase">
                {toolPart.type}
              </span>
              {durationMs !== undefined && (
                <span className="font-mono text-[11px] text-[var(--ink-subtle)]">
                  {durationMs}ms
                </span>
              )}
              {getStateBadge()}
            </div>
            <ChevronDown className={cn("h-3.5 w-3.5 text-[var(--ink-subtle)] transition-transform duration-150", isOpen && "rotate-180")} />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent
          className={cn(
            "border-t border-[var(--border)] bg-[var(--bg)]",
            "data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down overflow-hidden"
          )}
        >
          <div className="space-y-2.5 p-3 text-xs font-mono">
            {input && Object.keys(input).length > 0 && (
              <div>
                <span className="block text-[11px] uppercase tracking-wider text-[var(--ink-subtle)] mb-1">
                  Query Parameters
                </span>
                <div className="border border-[var(--border)] bg-[var(--surface)] p-2 space-y-1">
                  {Object.entries(input).map(([key, value]) => (
                    <div key={key} className="flex gap-2 leading-relaxed">
                      <span className="text-[var(--ink-subtle)] shrink-0">{key}:</span>
                      <span className="text-[var(--ink)] break-all">{formatValue(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {output && (
              <div>
                <span className="block text-[11px] uppercase tracking-wider text-[var(--ink-subtle)] mb-1">
                  Telemetry Response
                </span>
                <div className="border border-[var(--border)] bg-[var(--surface)] p-2 max-h-48 overflow-auto">
                  <pre className="whitespace-pre-wrap text-[11px] text-[var(--ink)] leading-relaxed">
                    {formatValue(output)}
                  </pre>
                </div>
              </div>
            )}

            {state === "output-error" && toolPart.errorText && (
              <div className="border border-red-500/30 bg-red-500/10 p-2 text-red-600 dark:text-red-400 text-xs">
                {toolPart.errorText}
              </div>
            )}

            {toolCallId && (
              <div className="border-t border-[var(--border)] pt-2 text-[10px] text-[var(--ink-subtle)]">
                Trace ID: {toolCallId}
              </div>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
