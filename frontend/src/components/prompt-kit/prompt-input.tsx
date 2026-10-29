"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

export interface PromptInputProps extends React.HTMLAttributes<HTMLDivElement> {
  error?: boolean;
}

export const PromptInput = React.forwardRef<HTMLDivElement, PromptInputProps>(
  ({ className, error, ...props }, ref) => (
    <div
      ref={ref}
      data-slot="prompt-input"
      className={cn(
        "group relative w-full border bg-[var(--surface)] text-[var(--ink)] shadow-none transition-[border-color,box-shadow] duration-140 ease-out",
        error
          ? "border-[var(--destructive)]"
          : "border-[var(--border-strong)] focus-within:border-[var(--accent)]",
        className
      )}
      style={{ borderRadius: 0 }}
      {...props}
    />
  )
);
PromptInput.displayName = "PromptInput";

export interface PromptInputFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {}

export const PromptInputField = React.forwardRef<HTMLInputElement, PromptInputFieldProps>(
  ({ className, type = "text", ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      data-slot="prompt-input-field"
      className={cn(
        "w-full bg-transparent px-4 py-3 sm:py-3.5 text-base sm:text-lg font-normal text-[var(--ink)] placeholder:text-[var(--ink-subtle)] focus:outline-none disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      style={{ borderRadius: 0 }}
      {...props}
    />
  )
);
PromptInputField.displayName = "PromptInputField";

export interface PromptInputActionsProps extends React.HTMLAttributes<HTMLDivElement> {}

export const PromptInputActions = React.forwardRef<HTMLDivElement, PromptInputActionsProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      data-slot="prompt-input-actions"
      className={cn(
        "flex flex-wrap items-center justify-between gap-2.5 border-t border-[var(--border)] bg-[var(--surface-subtle)] px-3 py-2.5 sm:px-4 sm:py-3",
        className
      )}
      style={{ borderRadius: 0 }}
      {...props}
    />
  )
);
PromptInputActions.displayName = "PromptInputActions";

export interface PromptInputActionProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  tooltip?: string;
}

export const PromptInputAction = React.forwardRef<HTMLButtonElement, PromptInputActionProps>(
  ({ className, tooltip, children, type = "button", ...props }, ref) => {
    const button = (
      <button
        ref={ref}
        type={type}
        data-slot="prompt-input-action"
        className={cn(
          "inline-flex items-center justify-center text-xs sm:text-sm font-medium transition-[background-color,border-color,color,transform] duration-140 ease-out active:scale-[0.98] cursor-pointer select-none disabled:pointer-events-none disabled:opacity-50 motion-reduce:transform-none motion-reduce:transition-none",
          className
        )}
        style={{ borderRadius: 0 }}
        {...props}
      >
        {children}
      </button>
    );

    if (!tooltip) return button;

    return (
      <Tooltip>
        <TooltipTrigger render={button} />
        <TooltipContent>{tooltip}</TooltipContent>
      </Tooltip>
    );
  }
);
PromptInputAction.displayName = "PromptInputAction";
