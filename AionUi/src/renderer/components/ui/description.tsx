/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import * as React from "react"
import { cn } from "@/lib/utils"

interface DescriptionItem {
  label: React.ReactNode
  value: React.ReactNode
}

interface DescriptionProps extends React.HTMLAttributes<HTMLDivElement> {
  items: DescriptionItem[]
  column?: 1 | 2 | 3 | 4
}

const Description = React.forwardRef<HTMLDivElement, DescriptionProps>(
  ({ className, items, column = 1, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "grid gap-x-8 gap-y-4",
        column === 1 && "grid-cols-1",
        column === 2 && "grid-cols-1 sm:grid-cols-2",
        column === 3 && "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
        column === 4 && "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4",
        className
      )}
      {...props}
    >
      {items.map((item, index) => (
        <div key={index} className="flex flex-col gap-1">
          <div className="text-sm text-muted-foreground">{item.label}</div>
          <div className="text-sm">{item.value}</div>
        </div>
      ))}
    </div>
  )
)
Description.displayName = "Description"

export { Description, type DescriptionItem }
