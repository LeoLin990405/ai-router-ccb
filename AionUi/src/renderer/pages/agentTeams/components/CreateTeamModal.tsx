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
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [maxTeammates, setMaxTeammates] = useState(5);
  const [strategy, setStrategy] = useState('round_robin');
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (visible) {
      setName('');
      setDescription('');
      setMaxTeammates(5);
      setStrategy('round_robin');
      setErrors({});
    }
  }, [visible]);

  const handleSubmit = async () => {
    const newErrors: Record<string, string> = {};
    if (!name.trim()) {
      newErrors.name = 'Team name is required';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    await onConfirm({
      name,
      description,
      max_teammates: maxTeammates,
      task_allocation_strategy: strategy,
    });
  };

  return (
    <Dialog open={visible} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            <Typography variant="h6">Create New Team</Typography>
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="team-name">Team Name</Label>
            <Input
              id="team-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Content Generation Team"
            />
            {errors.name && <p className="text-sm text-destructive">{errors.name}</p>}
          </div>
          <div className="space-y-2">
            <Label htmlFor="team-description">Description</Label>
            <textarea
              id="team-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What this team is for..."
              className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="max-teammates">Max Teammates</Label>
              <Input
                id="max-teammates"
                type="number"
                min={1}
                max={20}
                value={maxTeammates}
                onChange={(e) => setMaxTeammates(Number(e.target.value))}
              />
            </div>
            <div className="space-y-2">
              <Label>Allocation Strategy</Label>
              <Select value={strategy} onValueChange={setStrategy}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="round_robin">Round Robin</SelectItem>
                  <SelectItem value="load_balance">Load Balance</SelectItem>
                  <SelectItem value="skill_based">Skill Based</SelectItem>
                </SelectContent>
              </Select>
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
