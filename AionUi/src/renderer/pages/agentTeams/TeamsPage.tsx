/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Form, Input, InputNumber, Message, Modal, Space, Table, Tag } from '@arco-design/web-react';
import { motion } from 'framer-motion';
import { agentTeamsApi } from './api';
import type { IAgentTeam } from '@/common/ipcBridge';
import { Typography } from '@/renderer/components/atoms/Typography';

const TeamsPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [teams, setTeams] = useState<IAgentTeam[]>([]);
  const [visible, setVisible] = useState(false);

  const [form] = Form.useForm();

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await agentTeamsApi.listTeams();
      setTeams(data);
    } catch (error) {
      Message.error(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  };

  const createTeam = async () => {
    try {
      const values = await form.validate();
      await agentTeamsApi.createTeam(values);
      Message.success('Team created');
      setVisible(false);
      form.resetFields();
      await refresh();
    } catch (error) {
      if (error instanceof Error) {
        Message.error(error.message);
      }
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5 }}
      style={{ padding: '24px' }}
    >
      <div style={{ marginBottom: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Typography variant="h4" bold>Teams</Typography>
          <Typography variant="body2" color="secondary">Manage your AI agent teams</Typography>
        </div>
        <Button 
          type='primary' 
          onClick={() => setVisible(true)}
          style={{ borderRadius: 'var(--radius-md)' }}
        >
          Create Team
        </Button>
      </div>

      <Card 
        style={{ borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-md)' }}
        bodyStyle={{ padding: 0 }}
      >
        <Table
          loading={loading}
          rowKey='id'
          data={teams}
          pagination={{ pageSize: 10 }}
          columns={[
            {
              title: 'Name',
              dataIndex: 'name',
              render: (_: unknown, row: IAgentTeam) => (
                <Button
                  type='text'
                  onClick={() => {
                    void navigate(`/agent-teams/teams/${row.id}`);
                  }}
                  style={{ padding: 0, height: 'auto', fontWeight: 600, color: 'var(--color-primary)' }}
                >
                  {row.name}
                </Button>
              ),
            },
            { 
              title: 'Description', 
              dataIndex: 'description',
              render: (desc: string) => <Typography variant="body2" color="secondary">{desc || '-'}</Typography>
            },
            { title: 'Max Teammates', dataIndex: 'max_teammates' },
            {
              title: 'Strategy',
              dataIndex: 'task_allocation_strategy',
              render: (strategy: string) => <Tag style={{ borderRadius: 'var(--radius-sm)' }}>{strategy}</Tag>
            },
            {
              title: 'Status',
              dataIndex: 'status',
              render: (status: IAgentTeam['status']) => (
                <Tag 
                  color={status === 'active' ? 'green' : 'orange'}
                  style={{ borderRadius: 'var(--radius-sm)' }}
                >
                  {status}
                </Tag>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title={<Typography variant="h6">Create Team</Typography>}
        visible={visible}
        onCancel={() => setVisible(false)}
        style={{ borderRadius: 'var(--radius-lg)' }}
        onOk={() => {
          void createTeam();
        }}
      >
        <Form form={form} layout='vertical'>
          <Form.Item label='Team Name' field='name' rules={[{ required: true }]}> 
            <Input placeholder='e.g. Core Delivery Team' style={{ borderRadius: 'var(--radius-md)' }} />
          </Form.Item>
          <Form.Item label='Description' field='description'>
            <Input placeholder='Optional description' style={{ borderRadius: 'var(--radius-md)' }} />
          </Form.Item>
          <Form.Item label='Max Teammates' field='max_teammates' initialValue={5}>
            <InputNumber min={1} max={20} style={{ borderRadius: 'var(--radius-md)', width: '100%' }} />
          </Form.Item>
          <Form.Item label='Allocation Strategy' field='task_allocation_strategy' initialValue='round_robin'>
            <Input placeholder='round_robin / load_balance / skill_based' style={{ borderRadius: 'var(--radius-md)' }} />
          </Form.Item>
        </Form>
      </Modal>
    </motion.div>
  );
};

export default TeamsPage;
