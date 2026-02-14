import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/renderer/components/ui/dialog';
import { Button } from '@/renderer/components/ui/button';
import { Input } from '@/renderer/components/ui/input';
import { Label } from '@/renderer/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/renderer/components/ui/select';
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
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState(5);
  const [blockedBy, setBlockedBy] = useState<string[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (visible) {
      setSubject('');
      setDescription('');
      setPriority(5);
      setBlockedBy([]);
      setErrors({});
    }
  }, [visible]);

  const handleSubmit = async () => {
    const newErrors: Record<string, string> = {};
    if (!subject.trim()) {
      newErrors.subject = 'Subject is required';
    }
    if (!description.trim()) {
      newErrors.description = 'Description is required';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    await onConfirm({
      subject,
      description,
      priority,
      blocked_by: blockedBy,
    });
  };

  return (
    <Dialog open={visible} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>
            <Typography variant="h6">Create New Task</Typography>
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="task-subject">Subject</Label>
            <Input
              id="task-subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="What needs to be done?"
            />
            {errors.subject && <p className="text-sm text-destructive">{errors.subject}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="task-description">Description</Label>
            <textarea
              id="task-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Detailed instructions..."
              className="w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            />
            {errors.description && <p className="text-sm text-destructive">{errors.description}</p>}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="task-priority">Priority (1-10)</Label>
              <Input
                id="task-priority"
                type="number"
                min={1}
                max={10}
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label>Depends On</Label>
              <div className="flex flex-col gap-1 max-h-[100px] overflow-y-auto border rounded-md p-2">
                {existingTasks.length === 0 ? (
                  <span className="text-sm text-muted-foreground">No existing tasks</span>
                ) : (
                  existingTasks.map((task) => (
                    <label key={task.id} className="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="checkbox"
                        checked={blockedBy.includes(task.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setBlockedBy([...blockedBy, task.id]);
                          } else {
                            setBlockedBy(blockedBy.filter(id => id !== task.id));
                          }
                        }}
                        className="rounded border-gray-300"
                      />
                      <span className="truncate">{task.subject}</span>
                    </label>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={loading}>
            {loading ? 'Creating...' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
