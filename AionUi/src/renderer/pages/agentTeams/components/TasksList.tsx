/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { TaskCard } from './TaskCard';
import { Typography } from '@/renderer/components/atoms/Typography';
import type { IAgentTask } from '@/common/ipcBridge';

interface TasksListProps {
  tasks: IAgentTask[];
  onViewDetail?: (taskId: string) => void;
  onRun?: (taskId: string) => void;
}

export const TasksList: React.FC<TasksListProps> = ({ tasks, onViewDetail, onRun }) => {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: tasks.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 140, // 每个任务卡片高度约 140px
    overscan: 5, // 多渲染 5 个以防滚动卡顿
  });

  if (tasks.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-bg-1 rounded-lg border border-line-2">
        <Typography variant="body2" color="secondary">
          暂无任务
        </Typography>
      </div>
    );
  }

  return (
    <div
      ref={parentRef}
      className="h-full overflow-auto bg-bg-1 rounded-lg border border-line-2 p-4"
      style={{ maxHeight: '600px' }}
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: `${virtualItem.size}px`,
              transform: `translateY(${virtualItem.start}px)`,
              padding: '0 8px',
            }}
          >
            <TaskCard
              task={tasks[virtualItem.index]}
              onViewDetail={onViewDetail}
              onRun={onRun}
            />
          </div>
        ))}
      </div>
    </div>
  );
};
