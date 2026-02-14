/**
 * @license
 * Copyright 2025 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import type { TChatConversation } from '@/common/storage';
import { Toaster, toast } from 'sonner';
import React from 'react';
import ChatWorkspace from './workspace';

interface MessageApi {
  success: (content: string) => void;
  error: (content: string) => void;
  warning: (content: string) => void;
  info: (content: string) => void;
}

const ChatSider: React.FC<{
  conversation?: TChatConversation;
}> = ({ conversation }) => {
  const messageApi: MessageApi = {
    success: (content: string) => toast.success(content),
    error: (content: string) => toast.error(content),
    warning: (content: string) => toast.warning(content),
    info: (content: string) => toast.info(content),
  };

  let workspaceNode: React.ReactNode = null;
  if (conversation?.type === 'gemini') {
    workspaceNode = <ChatWorkspace conversation_id={conversation.id} workspace={conversation.extra.workspace} messageApi={messageApi}></ChatWorkspace>;
  } else if (conversation?.type === 'acp' && conversation.extra?.workspace) {
    workspaceNode = <ChatWorkspace conversation_id={conversation.id} workspace={conversation.extra.workspace} eventPrefix='acp' messageApi={messageApi}></ChatWorkspace>;
  } else if (conversation?.type === 'codex' && conversation.extra?.workspace) {
    workspaceNode = <ChatWorkspace conversation_id={conversation.id} workspace={conversation.extra.workspace} eventPrefix='codex' messageApi={messageApi}></ChatWorkspace>;
  } else if (conversation?.type === 'openclaw-gateway' && conversation.extra?.workspace) {
    workspaceNode = <ChatWorkspace conversation_id={conversation.id} workspace={conversation.extra.workspace} eventPrefix='openclaw-gateway' messageApi={messageApi}></ChatWorkspace>;
  } else if (conversation?.type === 'hivemind' && conversation.extra?.workspace) {
    workspaceNode = <ChatWorkspace conversation_id={conversation.id} workspace={conversation.extra.workspace} eventPrefix='hivemind' messageApi={messageApi}></ChatWorkspace>;
  }

  if (!workspaceNode) {
    return <div></div>;
  }

  return (
    <>
      <Toaster position="top-center" richColors closeButton />
      {workspaceNode}
    </>
  );
};

export default ChatSider;
