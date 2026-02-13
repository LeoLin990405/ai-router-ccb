import React from 'react';
import { Typography } from '@/renderer/components/atoms/Typography';

interface StatBadgeProps {
  label: string;
  value: string | number;
  color?: 'primary' | 'success' | 'warning' | 'error';
}

export const StatBadge: React.FC<StatBadgeProps> = ({ label, value, color = 'primary' }) => {
  const getColorVar = () => {
    switch (color) {
      case 'success': return 'var(--color-success)';
      case 'warning': return 'var(--color-warning)';
      case 'error': return 'var(--color-error)';
      default: return 'var(--color-primary)';
    }
  };

  return (
    <div style={{
      padding: '12px 16px',
      background: 'var(--bg-1)',
      borderRadius: 'var(--radius-md)',
      border: '1px solid var(--color-border)',
      display: 'flex',
      flexDirection: 'column',
      gap: '4px',
      flex: 1
    }}>
      <Typography variant="caption" color="secondary" bold>{label}</Typography>
      <Typography variant="h6" bold style={{ color: getColorVar() }}>{value}</Typography>
    </div>
  );
};
