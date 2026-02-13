import React from 'react';
import { Modal, Form, Input, InputNumber, Select } from '@arco-design/web-react';
import { Typography } from '@/renderer/components/atoms/Typography';

interface CreateTeamModalProps {
  visible: boolean;
  onCancel: () => void;
  onConfirm: (values: any) => Promise<void>;
  loading?: boolean;
}

export const CreateTeamModal: React.FC<CreateTeamModalProps> = ({
  visible,
  onCancel,
  onConfirm,
  loading
}) => {
  const [form] = Form.useForm();

  const handleOk = async () => {
    try {
      const values = await form.validate();
      await onConfirm(values);
      form.resetFields();
    } catch (error) {
      // Form validation error
    }
  };

  return (
    <Modal
      title={<Typography variant="h6">Create New Team</Typography>}
      visible={visible}
      onCancel={onCancel}
      onOk={handleOk}
      confirmLoading={loading}
      style={{ borderRadius: 'var(--radius-lg)' }}
    >
      <Form form={form} layout='vertical'>
        <Form.Item label='Team Name' field='name' rules={[{ required: true }]}>
          <Input placeholder='e.g. Content Generation Team' style={{ borderRadius: 'var(--radius-sm)' }} />
        </Form.Item>
        <Form.Item label='Description' field='description'>
          <Input.TextArea placeholder='What this team is for...' style={{ borderRadius: 'var(--radius-sm)' }} />
        </Form.Item>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <Form.Item label='Max Teammates' field='max_teammates' initialValue={5}>
            <InputNumber min={1} max={20} style={{ width: '100%', borderRadius: 'var(--radius-sm)' }} />
          </Form.Item>
          <Form.Item label='Allocation Strategy' field='task_allocation_strategy' initialValue='round_robin'>
            <Select style={{ borderRadius: 'var(--radius-sm)' }}>
              <Select.Option value='round_robin'>Round Robin</Select.Option>
              <Select.Option value='load_balance'>Load Balance</Select.Option>
              <Select.Option value='skill_based'>Skill Based</Select.Option>
            </Select>
          </Form.Item>
        </div>
      </Form>
    </Modal>
  );
};
