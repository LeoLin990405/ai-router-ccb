/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Badge } from '@/renderer/components/ui/badge';
import { Button } from '@/renderer/components/ui/button';
import { motion } from 'framer-motion';
import { Play, FileText, Connection } from '@icon-park/react';
import { Typography } from '@/renderer/components/atoms/Typography';
import type { IAgentTask } from '@/common/ipcBridge';
import IconParkHOC from '@/renderer/components/IconParkHOC';

interface TaskCardProps {
  task: IAgentTask;
  isDragging?: boolean;
  onViewDetail?: (taskId: string) => void;
  onRun?: (taskId: string) => void;
}

const IconPlay = IconParkHOC(Play);
const IconFile = IconParkHOC(FileText);
const IconLink = IconParkHOC(Connection);

// Provider 颜色映射
const PROVIDER_COLORS: Record<string, { color: string; bg: string }> = {
  claude: { color: '#0ea5e9', bg: '#0ea5e920' },
  kimi: { color: '#10b981', bg: '#10b98120' },
  gemini: { color: '#8b5cf6', bg: '#8b5cf620' },
  qwen: { color: '#f59e0b', bg: '#f59e0b20' },
  deepseek: { color: '#ef4444', bg: '#ef444420' },
};

// 优先级颜色
const getPriorityColor = (priority: number) => {
  if (priority >= 8) return { color: '#ef4444', bg: '#ef444420', label: '高' };
  if (priority >= 5) return { color: '#f59e0b', bg: '#f59e0b20', label: '中' };
  return { color: '#0ea5e9', bg: '#0ea5e920', label: '低' };
};

export const TaskCard: React.FC<TaskCardProps> = React.memo(({
  task,
  isDragging = false,
  onViewDetail,
  onRun,
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging: isSortableDragging,
  } = useSortable({ id: task.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const priorityConfig = getPriorityColor(task.priority);
  const providerConfig = task.provider ? PROVIDER_COLORS[task.provider] : null;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
    >
      <motion.div
        whileHover={{ scale: isDragging ? 1 : 1.02, y: -2 }}
        whileTap={{ scale: 0.98 }}
        className={`
          bg-bg-0 rounded-lg p-4 border border-line-2 shadow-sm
          cursor-grab active:cursor-grabbing
          hover:shadow-md hover:border-primary/30
          transition-all duration-200
          ${isSortableDragging || isDragging ? 'opacity-50 shadow-lg' : ''}
        `}
      >
        {/* 头部：优先级和 Provider */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Badge
              variant="outline"
              className="text-xs"
              style={{
                backgroundColor: priorityConfig.bg,
                color: priorityConfig.color,
                borderColor: priorityConfig.color,
              }}
            >
              P{task.priority} {priorityConfig.label}
            </Badge>
            {task.provider && providerConfig && (
              <Badge
                variant="outline"
                className="text-xs capitalize"
                style={{
                  backgroundColor: providerConfig.bg,
                  color: providerConfig.color,
                  borderColor: providerConfig.color,
                }}
              >
                {task.provider}
              </Badge>
            )}
          </div>
          
          {task.cost_usd > 0 && (
            <Typography variant="caption" className="text-t-secondary">
              ${task.cost_usd.toFixed(2)}
            </Typography>
          )}
        </div>

        {/* 标题 */}
        <Button
          variant="ghost"
          className="w-full p-0 h-auto text-left mb-2 hover:text-primary justify-start"
          onClick={(e) => {
            e.stopPropagation();
            onViewDetail?.(task.id);
          }}
        >
          <Typography variant="body2" bold className="text-t-primary line-clamp-2">
            {task.subject}
          </Typography>
        </Button>

        {/* 描述 */}
        <Typography variant="caption" color="secondary" className="line-clamp-2 mb-3 block">
          {task.description}
        </Typography>

        {/* 依赖指示器 */}
        {task.blocked_by.length > 0 && (
          <div className="flex items-center gap-1 mb-3 text-warning text-xs">
            <IconLink />
            <span>依赖 {task.blocked_by.length} 个任务</span>
          </div>
        )}

        {/* 底部操作栏 */}
        <div className="flex items-center justify-between pt-2 border-t border-line-2">
          <div className="flex items-center gap-2">
            {task.assigned_to && (
              <div className="flex items-center gap-1 text-xs text-t-secondary">
                <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center text-xs text-primary">
                  {task.assigned_to.substring(0, 1).toUpperCase()}
                </div>
                <span className="max-w-20 truncate">{task.assigned_to.substring(0, 8)}</span>
              </div>
            )}
          </div>

          {task.status !== 'completed' && task.status !== 'failed' && (
            <Button
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onRun?.(task.id);
              }}
              className="rounded-md gap-1"
            >
              <IconPlay />
              执行
            </Button>
          )}
        </div>

        {/* 状态标签 */}
        {task.status === 'completed' && (
          <div className="mt-2 flex items-center gap-1 text-xs text-success">
            <span className="w-1.5 h-1.5 rounded-full bg-success" />
            <span>已完成</span>
          </div>
        )}
        {task.status === 'failed' && (
          <div className="mt-2 flex items-center gap-1 text-xs text-error">
            <span className="w-1.5 h-1.5 rounded-full bg-error" />
            <span>失败</span>
          </div>
        )}
      </motion.div>
    </div>
  );
}, (prevProps, nextProps) => {
  // 自定义比较函数，只在必要时重新渲染
  return (
    prevProps.task.id === nextProps.task.id &&
    prevProps.task.status === nextProps.task.status &&
    prevProps.task.updated_at === nextProps.task.updated_at &&
    prevProps.isDragging === nextProps.isDragging
  );
});
