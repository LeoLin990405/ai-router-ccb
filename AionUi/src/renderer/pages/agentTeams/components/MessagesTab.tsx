import React from 'react';
import { Timeline, TimelineItem } from '@/renderer/components/ui/timeline';
import { Typography } from '@/renderer/components/atoms/Typography';
import type { IAgentTeamMessage } from '@/common/ipcBridge';

interface MessagesTabProps {
  messages: IAgentTeamMessage[];
}

export const MessagesTab: React.FC<MessagesTabProps> = ({ messages }) => {
  return (
    <div style={{ padding: '24px 0' }}>
      <Timeline>
        {messages.map((message) => (
          <TimelineItem 
            key={message.id} 
            label={<Typography variant="caption" color="secondary">{new Date(message.created_at).toLocaleString()}</Typography>}
          >
            <div style={{ background: 'var(--bg-1)', padding: 12, borderRadius: 'var(--radius-md)', border: '1px solid var(--color-border)' }}>
              <Typography variant="body2" bold style={{ marginBottom: 4 }}>{message.type.toUpperCase()}</Typography>
              <Typography variant="body2">{message.content}</Typography>
            </div>
          </TimelineItem>
        ))}
      </Timeline>
      {messages.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <Typography variant="body2" color="tertiary">No messages yet</Typography>
        </div>
      )}
    </div>
  );
};
