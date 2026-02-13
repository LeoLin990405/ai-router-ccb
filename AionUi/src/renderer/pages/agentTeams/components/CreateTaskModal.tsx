import React from 'react';
import { Modal, Form, Input, InputNumber, Select } from '@arco-design/web-react';
import { Typography } from '@/renderer/components/atoms/Typography';
import type { IAgentTask } from '@/common/ipcBridge';

interface CreateTaskModalProps {
  visible: boolean;
  onCancel: () => void;
  onConfirm: (values: any) => Promise<void>;
  loading?: boolean;
  existingTasks?: IAgentTask[];
}

export const CreateTaskModal: React.FC<CreateTaskModalProps> = ({
  visible,
  onCancel,
  onConfirm,
  loading,
  existingTasks = []
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
      title={<Typography variant="h6">Create New Task</Typography>}
      visible={visible}
      onCancel={onCancel}
      onOk={handleOk}
      confirmLoading={loading}
      style={{ borderRadius: 'var(--radius-lg)', width: '600px' }}
    >
      <Form form={form} layout='vertical'>
        <Form.Item label='Subject' field='subject' rules={[{ required: true }]}>
          <Input placeholder='What needs to be done?' style={{ borderRadius: 'var(--radius-sm)' }} />
        </Form.Item>
        <Form.Item label='Description' field='description' rules={[{ required: true }]}>
          <Input.TextArea placeholder='Detailed instructions...' style={{ borderRadius: 'var(--radius-sm)' }} />
        </Form.Item>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <Form.Item label='Priority (1-10)' field='priority' initialValue={5}>
            <InputNumber min={1} max={10} style={{ width: '100%', borderRadius: 'var(--radius-sm)' }} />
          </Form.Item>
          <Form.Item label='Depends On' field='blocked_by'>
            <Select mode='multiple' placeholder='Select dependencies' style={{ borderRadius: 'var(--radius-sm)' }} allowClear>
              {existingTasks.map(t => (
                <Select.Option key={t.id} value={t.id}>{t.subject}</Select.Option>
              ))}
            </Select>
          </Form.Item>
        </div>
      </Form>
    </Modal>
  );
};
