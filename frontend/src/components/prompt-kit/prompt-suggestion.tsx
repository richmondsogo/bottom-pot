"use client"

import * as React from "react"
import { Button, buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { type VariantProps } from "class-variance-authority"

export type PromptSuggestionProps = {
  children: React.ReactNode
  variant?: VariantProps<typeof buttonVariants>["variant"]
  size?: VariantProps<typeof buttonVariants>["size"]
  className?: string
  highlight?: string
} & React.ButtonHTMLAttributes<HTMLButtonElement>

export function PromptSuggestion({
  children,
  variant,
  size,
  className,
  highlight,
  ...props
}: PromptSuggestionProps) {
  const isHighlightMode = highlight !== undefined && highlight.trim() !== ""
  const content = typeof children === "string" ? children : ""

  if (!isHighlightMode) {
    return (
      <Button
        variant={variant || "outline"}
        size={size || "sm"}
        className={cn(
          "rounded-none! h-8 px-3 text-xs font-normal border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-colors",
          className
        )}
        {...props}
      >
        {children}
      </Button>
    )
  }

  if (!content) {
    return (
      <Button
        variant={variant || "ghost"}
        size={size || "sm"}
        className={cn(
          "w-full cursor-pointer justify-start rounded-none! py-1.5 px-2.5 text-xs text-[var(--ink)] hover:bg-[var(--surface-hover)]",
          className
        )}
        {...props}
      >
        {children}
      </Button>
    )
  }

  const trimmedHighlight = highlight.trim()
  const contentLower = content.toLowerCase()
  const highlightLower = trimmedHighlight.toLowerCase()
  const shouldHighlight = contentLower.includes(highlightLower)

  return (
    <Button
      variant={variant || "ghost"}
      size={size || "sm"}
      className={cn(
        "w-full cursor-pointer justify-start gap-0 rounded-none! py-1.5 px-2.5 text-xs text-[var(--ink)] hover:bg-[var(--surface-hover)]",
        className
      )}
      {...props}
    >
      {shouldHighlight ? (
        (() => {
          const index = contentLower.indexOf(highlightLower)
          if (index === -1)
            return (
              <span className="text-[var(--ink-muted)] whitespace-pre-wrap">
                {content}
              </span>
            )

          const actualHighlightedText = content.substring(
            index,
            index + highlightLower.length
          )

          const before = content.substring(0, index)
          const after = content.substring(index + actualHighlightedText.length)

          return (
            <>
              {before && (
                <span className="text-[var(--ink-muted)] whitespace-pre-wrap">
                  {before}
                </span>
              )}
              <span className="text-[var(--ink)] font-semibold whitespace-pre-wrap">
                {actualHighlightedText}
              </span>
              {after && (
                <span className="text-[var(--ink-muted)] whitespace-pre-wrap">
                  {after}
                </span>
              )}
            </>
          )
        })()
      ) : (
        <span className="text-[var(--ink-muted)] whitespace-pre-wrap">
          {content}
        </span>
      )}
    </Button>
  )
}
