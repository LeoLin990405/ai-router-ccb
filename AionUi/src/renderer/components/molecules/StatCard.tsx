import React from 'react';
import { Card } from '@arco-design/web-react';
import { Typography } from '../atoms/Typography';

interface StatCardProps {
  title: string;
  value: string | number;
  icon?: React.ReactNode;
  trend?: number;
  trendLabel?: string;
  color?: 'primary' | 'success' | 'warning' | 'error';
}

export const StatCard: React.FC<StatCardProps> = React.memo(({
  title,
  value,
  icon,
  trend,
  trendLabel,
  color = 'primary',
}) => {
  const getColorVar = () => {
    switch (color) {
      case 'success': return 'var(--color-success)';
      case 'warning': return 'var(--color-warning)';
      case 'error': return 'var(--color-error)';
      default: return 'var(--color-primary)';
    }
  };

  return (
    <Card
      style={{
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-sm)',
        border: '1px solid var(--color-border)',
      }}
      bodyStyle={{ padding: '20px' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Typography variant="caption" color="secondary" bold style={{ textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            {title}
          </Typography>
          <Typography variant="h4" bold style={{ marginTop: '8px', color: getColorVar() }}>
            {value}
          </Typography>
        </div>
        {icon && (
          <div style={{
            background: `${getColorVar()}15`,
            color: getColorVar(),
            padding: '10px',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {icon}
          </div>
        )}
      </div>
      {(trend !== undefined || trendLabel) && (
        <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          {trend !== undefined && (
            <Typography
              variant="caption"
              bold
              style={{
                color: trend >= 0 ? 'var(--color-success)' : 'var(--color-error)',
                display: 'flex',
                alignItems: 'center'
              }}
            >
              {trend >= 0 ? '+' : ''}{trend}%
            </Typography>
          )}
          {trendLabel && (
            <Typography variant="caption" color="tertiary">
              {trendLabel}
            </Typography>
          )}
        </div>
      )}
    </Card>
  );
}, (prevProps, nextProps) => {
  return (
    prevProps.value === nextProps.value &&
    prevProps.title === nextProps.title &&
    prevProps.trend === nextProps.trend
  );
});
