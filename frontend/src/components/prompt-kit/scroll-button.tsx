"use client"

import * as React from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { ArrowUp, ArrowDown } from "lucide-react"

export type ScrollButtonProps = {
  className?: string
  direction?: "up" | "down"
  targetId?: string
  threshold?: number
} & React.ButtonHTMLAttributes<HTMLButtonElement>

export function ScrollButton({
  className,
  direction = "up",
  targetId,
  threshold = 300,
  ...props
}: ScrollButtonProps) {
  const [visible, setVisible] = React.useState(false)

  React.useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY || document.documentElement.scrollTop
      if (direction === "up") {
        setVisible(scrollY > threshold)
      } else {
        const maxScroll = document.documentElement.scrollHeight - window.innerHeight
        setVisible(scrollY < maxScroll - threshold)
      }
    }

    window.addEventListener("scroll", handleScroll, { passive: true })
    handleScroll()
    return () => window.removeEventListener("scroll", handleScroll)
  }, [direction, threshold])

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    props.onClick?.(e)
    if (targetId) {
      const el = document.getElementById(targetId)
      if (el) {
        el.scrollIntoView({ behavior: "smooth" })
        return
      }
    }

    if (direction === "up") {
      window.scrollTo({ top: 0, behavior: "smooth" })
    } else {
      window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" })
    }
  }

  return (
    <Button
      variant="outline"
      size="sm"
      aria-label={direction === "up" ? "Scroll to top" : "Scroll to bottom"}
      className={cn(
        "fixed right-6 bottom-6 z-40 h-9 w-9 rounded-none! border border-[var(--border)] bg-[var(--surface)] text-[var(--ink)] shadow-md transition-all duration-150 ease-out hover:bg-[var(--surface-hover)]",
        visible
          ? "translate-y-0 scale-100 opacity-100"
          : "pointer-events-none translate-y-2 scale-95 opacity-0",
        className
      )}
      onClick={handleClick}
      {...props}
    >
      {direction === "up" ? (
        <ArrowUp className="h-4 w-4 text-[var(--ink)]" />
      ) : (
        <ArrowDown className="h-4 w-4 text-[var(--ink)]" />
      )}
    </Button>
  )
}
