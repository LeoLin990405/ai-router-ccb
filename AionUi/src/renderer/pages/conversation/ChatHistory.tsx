/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { ipcBridge } from '@/common';
import type { TChatConversation } from '@/common/storage';
import FlexFullContainer from '@/renderer/components/FlexFullContainer';
import { CronJobIndicator, useCronJobsMap } from '@/renderer/pages/cron';
import { addEventListener, emitter } from '@/renderer/utils/emitter';
import { getActivityTime, createTimelineGrouper } from '@/renderer/utils/timeline';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/renderer/components/ui/tooltip';
import { Input } from '@/renderer/components/ui/input';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/renderer/components/ui/alert-dialog';
import { Trash2, MessageSquare, Pencil } from 'lucide-react';
import classNames from 'classnames';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router-dom';

const useTimeline = () => {
  const { t } = useTranslation();
  return createTimelineGrouper(t);
};

const useScrollIntoView = (id: string) => {
  useEffect(() => {
    if (!id) return;
    const el = document.getElementById('c-' + id);
    if (!el) return;

    const findScrollParent = (node: HTMLElement | null): HTMLElement | null => {
      let p = node?.parentElement;
      while (p) {
        const style = window.getComputedStyle(p);
        const overflowY = style.overflowY;
        if (overflowY === 'auto' || overflowY === 'scroll') return p;
        p = p.parentElement;
      }
      return null;
    };

    const container = findScrollParent(el);

    const isOutOfView = (): boolean => {
      const elRect = el.getBoundingClientRect();
      if (!container) {
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
        return elRect.top < 0 || elRect.bottom > viewportHeight;
      }
      const cRect = container.getBoundingClientRect();
      return elRect.top < cRect.top || elRect.bottom > cRect.bottom;
    };

    if (isOutOfView()) {
      el.scrollIntoView({ block: 'nearest', behavior: 'auto' });
    }
  }, [id]);
};

const ChatHistory: React.FC<{ onSessionClick?: () => void; collapsed?: boolean }> = ({ onSessionClick, collapsed = false }) => {
  const [chatHistory, setChatHistory] = useState<TChatConversation[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState<string>('');
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { getJobStatus } = useCronJobsMap();

  useScrollIntoView(id);

  const handleSelect = (conversation: TChatConversation) => {
    Promise.resolve(navigate(`/conversation/${conversation.id}`)).catch((error) => {
      console.error('Navigation failed:', error);
    });
    // 点击session后自动隐藏sidebar
    if (onSessionClick) {
      onSessionClick();
    }
  };

  const isConversation = !!id;

  useEffect(() => {
    const refresh = () => {
      // Get conversations from database instead of file storage
      ipcBridge.database.getUserConversations
        .invoke({ page: 0, pageSize: 10000 })
        .then((history) => {
          if (history && Array.isArray(history) && history.length > 0) {
            const sortedHistory = history.sort((a, b) => getActivityTime(b) - getActivityTime(a));
            setChatHistory(sortedHistory);
          } else {
            setChatHistory([]);
          }
        })
        .catch((error) => {
          console.error('[ChatHistory] Failed to load conversations from database:', error);
          setChatHistory([]);
        });
    };
    refresh();
    return addEventListener('chat.history.refresh', refresh);
  }, [isConversation]);

  const handleRemoveConversation = (id: string) => {
    void ipcBridge.conversation.remove
      .invoke({ id })
      .then((success) => {
        if (success) {
          // Trigger refresh to reload from database
          emitter.emit('chat.history.refresh');
          void Promise.resolve(navigate('/')).catch((error) => {
            console.error('Navigation failed:', error);
          });
        }
      })
      .catch((error) => {
        console.error('Failed to remove conversation:', error);
      });
  };

  const handleEditStart = (conversation: TChatConversation) => {
    setEditingId(conversation.id);
    setEditingName(conversation.name);
  };

  const handleEditSave = async () => {
    if (!editingId || !editingName.trim()) return;

    try {
      const success = await ipcBridge.conversation.update.invoke({
        id: editingId,
        updates: { name: editingName.trim() },
      });

      if (success) {
        // Trigger refresh to reload from database
        emitter.emit('chat.history.refresh');
      }
    } catch (error) {
      console.error('Failed to update conversation name:', error);
    } finally {
      setEditingId(null);
      setEditingName('');
    }
  };

  const handleEditCancel = () => {
    setEditingId(null);
    setEditingName('');
  };

  const handleEditKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      void handleEditSave();
    } else if (e.key === 'Escape') {
      handleEditCancel();
    }
  };

  const formatTimeline = useTimeline();

  const renderConversation = (conversation: TChatConversation) => {
    const isSelected = id === conversation.id;
    const isEditing = editingId === conversation.id;
    const cronStatus = getJobStatus(conversation.id);

    return (
      <TooltipProvider key={conversation.id}>
        <Tooltip delayDuration={0}>
          <TooltipTrigger asChild>
            <div
              id={'c-' + conversation.id}
              className={classNames('chat-history__item hover:bg-hover px-3 py-2 rounded-lg flex justify-start items-center group cursor-pointer relative overflow-hidden shrink-0 conversation-item [&.conversation-item+&.conversation-item]:mt-0.5', {
                'bg-active': isSelected,
              })}
              onClick={handleSelect.bind(null, conversation)}
            >
              <MessageSquare size={20} className='mt-0.5 flex shrink-0' />
              <FlexFullContainer className='h-6 collapsed-hidden ml-2.5'>
                {isEditing ? (
                  <Input 
                    className='chat-history__item-editor text-sm leading-6 h-6 w-full' 
                    value={editingName} 
                    onChange={(e) => setEditingName(e.target.value)} 
                    onKeyDown={handleEditKeyDown} 
                    onBlur={handleEditSave} 
                    autoFocus 
                  />
                ) : (
                  <div className='flex items-center gap-1 w-full'>
                    <div className='chat-history__item-name text-nowrap overflow-hidden inline-block flex-1 text-sm leading-6 whitespace-nowrap'>{conversation.name}</div>
                    <CronJobIndicator status={cronStatus} size={14} />
                  </div>
                )}
              </FlexFullContainer>
              {!isEditing && (
                <div
                  className={classNames('absolute right-0 top-0 h-full w-[70px] items-center justify-end hidden group-hover:flex collapsed-hidden pr-3')}
                  style={{
                    backgroundImage: isSelected ? `linear-gradient(to right, transparent, var(--aou-2) 50%)` : `linear-gradient(to right, transparent, var(--aou-1) 50%)`,
                  }}
                  onClick={(event) => {
                    event.stopPropagation();
                  }}
                >
                  <span
                    className='flex-center mr-2'
                    onClick={(event) => {
                      event.stopPropagation();
                      handleEditStart(conversation);
                    }}
                  >
                    <Pencil size={20} className='flex' />
                  </span>
                  <AlertDialog open={deleteTargetId === conversation.id} onOpenChange={(open) => !open && setDeleteTargetId(null)}>
                    <AlertDialogTrigger asChild>
                      <span
                        className='flex-center'
                        onClick={(event) => {
                          event.stopPropagation();
                          setDeleteTargetId(conversation.id);
                        }}
                      >
                        <Trash2 size={20} className='flex' />
                      </span>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>{t('conversation.history.deleteTitle')}</AlertDialogTitle>
                        <AlertDialogDescription>
                          {t('conversation.history.deleteConfirm')}
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel onClick={(e) => {
                          e.stopPropagation();
                          setDeleteTargetId(null);
                        }}>
                          {t('conversation.history.cancelDelete')}
                        </AlertDialogCancel>
                        <AlertDialogAction onClick={(e) => {
                          e.stopPropagation();
                          handleRemoveConversation(conversation.id);
                          setDeleteTargetId(null);
                        }} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                          {t('conversation.history.confirmDelete')}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              )}
            </div>
          </TooltipTrigger>
          {collapsed && (
            <TooltipContent side="right">
              <p>{conversation.name || t('conversation.welcome.newConversation')}</p>
            </TooltipContent>
          )}
        </Tooltip>
      </TooltipProvider>
    );
  };

  return (
    <FlexFullContainer>
      <div
        className={classNames('size-full chat-history', {
          'flex items-center justify-center': !chatHistory.length,
          'flex flex-col overflow-y-auto': !!chatHistory.length,
          'chat-history--collapsed': collapsed,
        })}
      >
        {!chatHistory.length ? (
          <div className='chat-history__placeholder flex flex-col items-center justify-center text-muted-foreground'>
            <MessageSquare size={48} className='mb-2 opacity-50' />
            <p>{t('conversation.history.noHistory')}</p>
          </div>
        ) : (
          chatHistory.map((item) => {
            const timeline = formatTimeline(item);
            return (
              <React.Fragment key={item.id}>
                {timeline && <div className='chat-history__section px-3 py-2 text-sm text-muted-foreground font-bold'>{timeline}</div>}
                {renderConversation(item)}
              </React.Fragment>
            );
          })
        )}
      </div>
    </FlexFullContainer>
  );
};

export default ChatHistory;
