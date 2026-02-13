/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { motion } from 'framer-motion';
import { Typography } from '@/renderer/components/atoms/Typography';
import { TaskCard } from './TaskCard';
import type { IAgentTask } from '@/common/ipcBridge';

interface KanbanColumnProps {
  id: string;
  title: string;
  tasks: IAgentTask[];
  onViewDetail?: (taskId: string) => void;
  onRun?: (taskId: string) => void;
}

// 状态配置
const STATUS_CONFIG: Record<string, { label: string; color: string; bgColor: string }> = {
  pending: { label: '待处理', color: '#94a3b8', bgColor: '#94a3b820' },
  in_progress: { label: '进行中', color: '#0ea5e9', bgColor: '#0ea5e920' },
  completed: { label: '已完成', color: '#10b981', bgColor: '#10b98120' },
  failed: { label: '失败', color: '#ef4444', bgColor: '#ef444420' },
  cancelled: { label: '已取消', color: '#6b7280', bgColor: '#6b728020' },
};

export const KanbanColumn: React.FC<KanbanColumnProps> = ({
  id,
  title,
  tasks,
  onViewDetail,
  onRun,
}) => {
  const { setNodeRef, isOver } = useDroppable({ id });
  const config = STATUS_CONFIG[id] || { label: title, color: '#94a3b8', bgColor: '#94a3b820' };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col w-80 flex-shrink-0"
      style={{
        background: 'var(--bg-1)',
        borderRadius: 'var(--radius-lg)',
        border: `1px solid ${isOver ? config.color : 'var(--color-border)'}`,
        boxShadow: isOver ? `0 0 0 2px ${config.color}40` : 'var(--shadow-sm)',
        transition: 'all 0.2s ease',
      }}
    >
      {/* 列头部 */}
      <div
        className="p-4 border-b border-line-2"
        style={{
          borderTop: `3px solid ${config.color}`,
          borderRadius: 'var(--radius-lg) var(--radius-lg) 0 0',
        }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Typography variant="body1" bold className="text-t-primary">
              {config.label}
            </Typography>
            <span
              className="px-2 py-0.5 text-xs font-medium rounded-full"
              style={{
                backgroundColor: config.bgColor,
                color: config.color,
              }}
            >
              {tasks.length}
            </span>
          </div>
          <div
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: config.color }}
          />
        </div>
      </div>

      {/* 列内容区域 */}
      <div
        ref={setNodeRef}
        className="flex-1 p-4 space-y-3 min-h-[400px] max-h-[calc(100vh-300px)] overflow-y-auto"
        style={{
          backgroundColor: isOver ? `${config.color}08` : 'transparent',
          transition: 'background-color 0.2s ease',
          borderRadius: '0 0 var(--radius-lg) var(--radius-lg)',
        }}
      >
        <SortableContext
          id={id}
          items={tasks.map((t) => t.id)}
          strategy={verticalListSortingStrategy}
        >
          {tasks.map((task, index) => (
            <motion.div
              key={task.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2, delay: index * 0.05 }}
            >
              <TaskCard
                task={task}
                onViewDetail={onViewDetail}
                onRun={onRun}
              />
            </motion.div>
          ))}
        </SortableContext>
        
        {tasks.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center h-32 border-2 border-dashed border-line-2 rounded-lg"
          >
            <Typography variant="caption" color="tertiary">
              拖拽任务到此处
            </Typography>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
};
