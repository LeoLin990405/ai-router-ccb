import React from 'react';
import { Badge } from '@/renderer/components/ui/badge';
import { motion } from 'framer-motion';
import { Typography } from '@/renderer/components/atoms/Typography';
import type { IAgentTeammate } from '@/common/ipcBridge';

interface TeammateCardProps {
  teammate: IAgentTeammate;
}

export const TeammateCard: React.FC<TeammateCardProps> = ({ teammate }) => {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      style={{
        padding: 16,
        background: 'var(--bg-1)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--color-border)',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="body1" bold>{teammate.name}</Typography>
        <Badge 
          variant={teammate.status === 'idle' ? 'default' : 'secondary'}
        >
          {teammate.status.toUpperCase()}
        </Badge>
      </div>
      
      <Typography variant="body2" color="secondary">{teammate.role}</Typography>
      
      <div style={{ marginTop: '4px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <Badge variant="outline">{teammate.provider}</Badge>
        <Badge variant="outline">{teammate.model}</Badge>
      </div>

      {teammate.skills.length > 0 && (
        <div style={{ marginTop: '8px', display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {teammate.skills.map(skill => (
            <Badge key={skill} variant="secondary">
              {skill}
            </Badge>
          ))}
        </div>
      )}
    </motion.div>
  );
};
