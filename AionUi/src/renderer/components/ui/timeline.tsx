/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import * as React from "react"
import { cn } from "@/lib/utils"

const Timeline = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("flex flex-col gap-4", className)} {...props} />
))
Timeline.displayName = "Timeline"

const TimelineItem = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & {
    label?: React.ReactNode
  }
>(({ className, label, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("relative flex gap-4 pb-4 last:pb-0", className)}
    {...props}
  >
    <div className="flex flex-col items-center">
      <div className="h-3 w-3 rounded-full border-2 border-primary bg-background" />
      <div className="mt-2 h-full w-px bg-border" />
    </div>
    <div className="flex-1 space-y-1">
      {label && (
        <div className="text-xs text-muted-foreground">{label}</div>
      )}
      <div>{children}</div>
    </div>
  </div>
))
TimelineItem.displayName = "TimelineItem"

export { Timeline, TimelineItem }
