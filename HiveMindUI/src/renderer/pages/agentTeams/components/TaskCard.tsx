/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Badge } from '@/renderer/components/ui/badge';
import { Button } from '@/renderer/components/ui/button';
import { motion } from 'framer-motion';
import { Play, Connection } from '@icon-park/react';
import { Typography } from '@/renderer/components/atoms/Typography';
import type { IAgentTask } from '@/common/ipcBridge';
import IconParkHOC from '@/renderer/components/IconParkHOC';
import classNames from 'classnames';

interface TaskCardProps {
  task: IAgentTask;
  isDragging?: boolean;
  onViewDetail?: (taskId: string) => void;
  onRun?: (taskId: string) => void;
}

const IconPlay = IconParkHOC(Play);
const IconLink = IconParkHOC(Connection);

const PROVIDER_COLORS: Record<string, { color: string; bg: string }> = {
  claude: { color: '#0ea5e9', bg: '#0ea5e920' },
  kimi: { color: '#10b981', bg: '#10b98120' },
  gemini: { color: '#8b5cf6', bg: '#8b5cf620' },
  qwen: { color: '#f59e0b', bg: '#f59e0b20' },
};

const getPriorityColor = (priority: number) => {
  if (priority >= 8) return { color: '#ef4444', bg: '#ef444420', label: '高' };
  if (priority >= 5) return { color: '#f59e0b', bg: '#f59e0b20', label: '中' };
  return { color: '#0ea5e9', bg: '#0ea5e920', label: '低' };
};

export const TaskCard: React.FC<TaskCardProps> = React.memo(
  ({ task, isDragging = false, onViewDetail, onRun }) => {
    const { attributes, listeners, setNodeRef, transform, transition, isDragging: isSortableDragging } = useSortable({ id: task.id });

    const style = {
      transform: CSS.Transform.toString(transform),
      transition,
    };

    const priorityConfig = getPriorityColor(task.priority);
    const providerConfig = task.provider ? PROVIDER_COLORS[task.provider] : null;

    return (
      <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
        <motion.div
          whileHover={{ scale: isDragging ? 1 : 1.02, y: -2 }}
          whileTap={{ scale: 0.98 }}
          className={classNames('hive-agent-task-card', {
            'hive-agent-task-card--dragging opacity-50': isSortableDragging || isDragging,
          })}
        >
          <div className='hive-agent-task-card__header'>
            <div className='flex items-center gap-2'>
              <Badge
                variant='outline'
                className='text-xs'
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
                  variant='outline'
                  className='text-xs capitalize'
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
              <Typography variant='caption' className='text-t-secondary'>
                ${task.cost_usd.toFixed(2)}
              </Typography>
            )}
          </div>

          <Button
            variant='ghost'
            className='w-full p-0 h-auto text-left mb-2 hover:text-primary justify-start'
            onClick={(e) => {
              e.stopPropagation();
              onViewDetail?.(task.id);
            }}
          >
            <Typography variant='body2' bold className='text-t-primary line-clamp-2'>
              {task.subject}
            </Typography>
          </Button>

          <Typography variant='caption' color='secondary' className='line-clamp-2 mb-3 block'>
            {task.description}
          </Typography>

          {task.blocked_by.length > 0 && (
            <div className='hive-agent-task-card__dependency'>
              <IconLink />
              <span>依赖 {task.blocked_by.length} 个任务</span>
            </div>
          )}

          <div className='hive-agent-task-card__footer'>
            <div className='flex items-center gap-2'>
              {task.assigned_to && (
                <div className='hive-agent-task-card__assignee'>
                  <div className='hive-agent-task-card__assignee-avatar'>{task.assigned_to.substring(0, 1).toUpperCase()}</div>
                  <span className='max-w-20 truncate'>{task.assigned_to.substring(0, 8)}</span>
                </div>
              )}
            </div>

            {task.status !== 'completed' && task.status !== 'failed' && (
              <Button
                size='sm'
                onClick={(e) => {
                  e.stopPropagation();
                  onRun?.(task.id);
                }}
                className='rounded-md gap-1'
              >
                <IconPlay />
                执行
              </Button>
            )}
          </div>

          {task.status === 'completed' && (
            <div className='hive-agent-task-card__status hive-agent-task-card__status--completed'>
              <span className='hive-agent-task-card__status-dot' />
              <span>已完成</span>
            </div>
          )}
          {task.status === 'failed' && (
            <div className='hive-agent-task-card__status hive-agent-task-card__status--failed'>
              <span className='hive-agent-task-card__status-dot' />
              <span>失败</span>
            </div>
          )}
        </motion.div>
      </div>
    );
  },
  (prevProps, nextProps) => {
    return prevProps.task.id === nextProps.task.id && prevProps.task.status === nextProps.task.status && prevProps.task.updated_at === nextProps.task.updated_at && prevProps.isDragging === nextProps.isDragging;
  }
);
