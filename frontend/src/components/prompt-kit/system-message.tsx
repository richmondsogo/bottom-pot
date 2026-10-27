"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { cva, type VariantProps } from "class-variance-authority"
import { AlertCircle, AlertTriangle, Info } from "lucide-react"

const systemMessageVariants = cva(
  "flex flex-row items-center gap-3 rounded-none! border py-2 px-3 text-xs",
  {
    variants: {
      variant: {
        action: "text-[var(--ink)] border-[var(--border)] bg-[var(--surface)]",
        error: "text-red-700 dark:text-red-400 border-red-500/30 bg-red-500/10",
        warning: "text-amber-800 dark:text-amber-300 border-amber-500/30 bg-amber-500/10",
      },
      fill: {
        true: "bg-[var(--surface)]",
        false: "",
      },
    },
    defaultVariants: {
      variant: "action",
      fill: false,
    },
  }
)

export type SystemMessageProps = React.ComponentProps<"div"> &
  VariantProps<typeof systemMessageVariants> & {
    icon?: React.ReactNode
    isIconHidden?: boolean
    cta?: {
      label: string
      onClick?: () => void
      variant?: "solid" | "outline" | "ghost"
    }
  }

export function SystemMessage({
  children,
  variant = "action",
  fill = false,
  icon,
  isIconHidden = false,
  cta,
  className,
  ...props
}: SystemMessageProps) {
  const getDefaultIcon = () => {
    if (isIconHidden) return null

    switch (variant) {
      case "error":
        return <AlertCircle className="size-4 shrink-0 text-red-600 dark:text-red-400" />
      case "warning":
        return <AlertTriangle className="size-4 shrink-0 text-amber-600 dark:text-amber-400" />
      default:
        return <Info className="size-4 shrink-0 text-[var(--accent)]" />
    }
  }

  const getIconToShow = () => {
    if (isIconHidden) return null
    if (icon) return icon
    return getDefaultIcon()
  }

  const shouldShowIcon = getIconToShow() !== null

  return (
    <div
      className={cn(systemMessageVariants({ variant, fill }), className)}
      {...props}
    >
      <div className="flex flex-1 flex-row items-center gap-2.5 leading-normal">
        {shouldShowIcon && (
          <div className="flex shrink-0 items-center justify-center">
            {getIconToShow()}
          </div>
        )}

        <div className="flex min-w-0 flex-1 items-center">
          <div className="text-xs">{children}</div>
        </div>
      </div>

      {cta && (
        <Button
          variant="outline"
          size="sm"
          onClick={cta.onClick}
          className="rounded-none! h-7 px-2.5 text-xs border-[var(--border)] hover:bg-[var(--surface-hover)]"
        >
          {cta.label}
        </Button>
      )}
    </div>
  )
}
