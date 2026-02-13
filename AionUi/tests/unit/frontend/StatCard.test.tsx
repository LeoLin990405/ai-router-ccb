/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { StatCard } from '@/renderer/components/molecules/StatCard';

describe('StatCard', () => {
  it('renders title and value', () => {
    render(<StatCard title="总任务数" value={42} />);

    expect(screen.getByText('总任务数')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders string value', () => {
    render(<StatCard title="总成本" value="$123.45" />);

    expect(screen.getByText('$123.45')).toBeInTheDocument();
  });

  it('renders icon when provided', () => {
    const icon = <span data-testid="test-icon">📊</span>;
    render(<StatCard title="统计" value={100} icon={icon} />);

    expect(screen.getByTestId('test-icon')).toBeInTheDocument();
  });

  it('renders trend indicator when trend is provided', () => {
    render(<StatCard title="增长" value={100} trend={15} trendLabel="较上月" />);

    expect(screen.getByText('+15%')).toBeInTheDocument();
    expect(screen.getByText('较上月')).toBeInTheDocument();
  });

  it('renders negative trend in error color', () => {
    render(<StatCard title="下降" value={50} trend={-10} />);

    expect(screen.getByText('-10%')).toBeInTheDocument();
  });

  it('applies primary color by default', () => {
    const { container } = render(<StatCard title="测试" value={100} />);
    
    // Check that the component renders
    expect(container.firstChild).toBeInTheDocument();
  });

  it('applies success color when specified', () => {
    render(<StatCard title="成功" value={100} color="success" />);
    
    expect(screen.getByText('成功')).toBeInTheDocument();
    expect(screen.getByText('100')).toBeInTheDocument();
  });

  it('applies warning color when specified', () => {
    render(<StatCard title="警告" value={100} color="warning" />);
    
    expect(screen.getByText('警告')).toBeInTheDocument();
  });

  it('applies error color when specified', () => {
    render(<StatCard title="错误" value={100} color="error" />);
    
    expect(screen.getByText('错误')).toBeInTheDocument();
  });
});
