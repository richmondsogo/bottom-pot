"use client"

import * as React from "react"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"
import { ChevronDown } from "lucide-react"

export type StepsItemProps = React.ComponentProps<"div">

export const StepsItem = ({
  children,
  className,
  ...props
}: StepsItemProps) => (
  <div className={cn("text-[var(--ink-muted)] text-xs font-sans leading-relaxed", className)} {...props}>
    {children}
  </div>
)

export type StepsTriggerProps = React.ComponentProps<
  typeof CollapsibleTrigger
> & {
  leftIcon?: React.ReactNode
  swapIconOnHover?: boolean
}

export const StepsTrigger = ({
  children,
  className,
  leftIcon,
  swapIconOnHover = true,
  ...props
}: StepsTriggerProps) => (
  <CollapsibleTrigger
    className={cn(
      "group text-[var(--ink-muted)] hover:text-[var(--ink)] flex w-full cursor-pointer items-center justify-start gap-1 text-xs font-mono transition-colors",
      className
    )}
    {...props}
  >
    <div className="flex items-center gap-1.5">
      {leftIcon ? (
        <span className="relative inline-flex size-3.5 items-center justify-center">
          <span
            className={cn(
              "transition-opacity",
              swapIconOnHover && "group-hover:opacity-0"
            )}
          >
            {leftIcon}
          </span>
          {swapIconOnHover && (
            <ChevronDown className="absolute size-3.5 opacity-0 transition-opacity group-hover:opacity-100 group-data-[state=open]:rotate-180" />
          )}
        </span>
      ) : null}
      <span>{children}</span>
    </div>
    {!leftIcon && (
      <ChevronDown className="size-3.5 transition-transform duration-150 group-data-[state=open]:rotate-180" />
    )}
  </CollapsibleTrigger>
)

export type StepsContentProps = React.ComponentProps<
  typeof CollapsibleContent
> & {
  bar?: React.ReactNode
}

export const StepsContent = ({
  children,
  className,
  bar,
  ...props
}: StepsContentProps) => {
  return (
    <CollapsibleContent
      className={cn(
        "text-[var(--ink)] data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down overflow-hidden",
        className
      )}
      {...props}
    >
      <div className="mt-2.5 grid max-w-full min-w-0 grid-cols-[min-content_minmax(0,1fr)] items-start gap-x-2.5">
        <div className="min-w-0 self-stretch">{bar ?? <StepsBar />}</div>
        <div className="min-w-0 space-y-2">{children}</div>
      </div>
    </CollapsibleContent>
  )
}

export type StepsBarProps = React.HTMLAttributes<HTMLDivElement>

export const StepsBar = ({ className, ...props }: StepsBarProps) => (
  <div
    className={cn("bg-[var(--border)] h-full w-[1px] ml-1.5", className)}
    aria-hidden
    {...props}
  />
)

export type StepsProps = React.ComponentProps<typeof Collapsible>

export function Steps({ defaultOpen = true, className, ...props }: StepsProps) {
  return (
    <Collapsible
      className={cn(className)}
      defaultOpen={defaultOpen}
      {...props}
    />
  )
}
