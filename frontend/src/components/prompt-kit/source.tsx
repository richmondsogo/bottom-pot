"use client"

import * as React from "react"
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"
import { cn } from "@/lib/utils"
import { ExternalLink, ShieldCheck } from "lucide-react"

const SourceContext = React.createContext<{
  href: string
  domain: string
} | null>(null)

function useSourceContext() {
  const ctx = React.useContext(SourceContext)
  if (!ctx) throw new Error("Source.* must be used inside <Source>")
  return ctx
}

export type SourceProps = {
  href: string
  children: React.ReactNode
}

export function Source({ href, children }: SourceProps) {
  let domain = ""
  try {
    domain = new URL(href).hostname
  } catch {
    domain = href.split("/").pop() || href
  }

  return (
    <SourceContext.Provider value={{ href, domain }}>
      <HoverCard openDelay={150} closeDelay={100}>
        {children}
      </HoverCard>
    </SourceContext.Provider>
  )
}

export type SourceTriggerProps = {
  label?: string | number
  showFavicon?: boolean
  className?: string
  children?: React.ReactNode
}

export function SourceTrigger({
  label,
  showFavicon = false,
  className,
  children,
}: SourceTriggerProps) {
  const { href, domain } = useSourceContext()
  const labelToShow = label ?? domain.replace("www.", "")

  return (
    <HoverCardTrigger asChild>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(
          "inline-flex items-center gap-1.5 rounded-none! font-mono text-[11px] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:underline",
          className
        )}
      >
        {children ? (
          children
        ) : (
          <>
            {showFavicon && (
              <img
                src={`https://www.google.com/s2/favicons?sz=64&domain_url=${encodeURIComponent(
                  href
                )}`}
                alt=""
                width={12}
                height={12}
                className="size-3 rounded-none! grayscale opacity-70"
              />
            )}
            <span className="truncate">{labelToShow}</span>
          </>
        )}
      </a>
    </HoverCardTrigger>
  )
}

export type SourceContentProps = {
  title?: string
  description?: string
  verifiedAts?: boolean
  evidenceSnippet?: string
  className?: string
}

export function SourceContent({
  title,
  description,
  verifiedAts = true,
  evidenceSnippet,
  className,
}: SourceContentProps) {
  const { href, domain } = useSourceContext()

  return (
    <HoverCardContent
      align="start"
      side="top"
      className={cn("w-80 rounded-none! p-3 border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] shadow-md space-y-2 font-sans", className)}
    >
      <div className="flex items-center justify-between border-b border-[var(--border)] pb-1.5">
        <div className="flex items-center gap-1.5 font-mono text-[11px] text-[var(--ink)] font-medium">
          {verifiedAts && <ShieldCheck className="h-3.5 w-3.5 text-[var(--accent)]" />}
          <span className="truncate">{domain}</span>
        </div>
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[var(--ink-subtle)] hover:text-[var(--ink)]"
          aria-label="Open source directly"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      </div>

      {title && (
        <p className="text-xs font-semibold text-[var(--ink)] line-clamp-1">
          {title}
        </p>
      )}

      {description && (
        <p className="text-[11px] text-[var(--ink-muted)] line-clamp-2 leading-relaxed">
          {description}
        </p>
      )}

      {evidenceSnippet && (
        <div className="border border-[var(--border)] bg-[var(--bg)] p-2 text-[11px] font-mono text-[var(--ink-muted)] leading-relaxed">
          <span className="block text-[10px] uppercase text-[var(--ink-subtle)] mb-0.5">Verified Requisition Evidence:</span>
          <span className="italic line-clamp-3">"{evidenceSnippet}"</span>
        </div>
      )}
    </HoverCardContent>
  )
}
