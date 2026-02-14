/**
 * @license
 * Copyright 2026 AionUi (aionui.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/renderer/components/ui/button';
import { Input } from '@/renderer/components/ui/input';
import { Label } from '@/renderer/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/renderer/components/ui/dialog';
import { Card, CardContent, CardHeader, CardTitle } from '@/renderer/components/ui/card';
import { Badge } from '@/renderer/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/renderer/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/renderer/components/ui/table';
import { motion } from 'framer-motion';
import { agentTeamsApi } from './api';
import type { IAgentTeam } from '@/common/ipcBridge';
import { Typography } from '@/renderer/components/atoms/Typography';

const TeamsPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [teams, setTeams] = useState<IAgentTeam[]>([]);
  const [visible, setVisible] = useState(false);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [maxTeammates, setMaxTeammates] = useState(5);
  const [strategy, setStrategy] = useState<'round_robin' | 'load_balance' | 'skill_based'>('round_robin');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await agentTeamsApi.listTeams();
      setTeams(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const createTeam = async () => {
    const newErrors: Record<string, string> = {};
    if (!name.trim()) {
      newErrors.name = 'Team name is required';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    try {
      await agentTeamsApi.createTeam({
        name,
        description,
        max_teammates: maxTeammates,
        task_allocation_strategy: strategy,
      });
      setVisible(false);
      setName('');
      setDescription('');
      setMaxTeammates(5);
      setStrategy('round_robin');
      setErrors({});
      await refresh();
    } catch (error) {
      console.error(error);
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
        <Button onClick={() => setVisible(true)}>
          Create Team
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Max Teammates</TableHead>
                <TableHead>Strategy</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {teams.map((team) => (
                <TableRow key={team.id}>
                  <TableCell>
                    <Button
                      variant="link"
                      onClick={() => {
                        void navigate(`/agent-teams/teams/${team.id}`);
                      }}
                      className="p-0 h-auto font-semibold"
                    >
                      {team.name}
                    </Button>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="secondary">{team.description || '-'}</Typography>
                  </TableCell>
                  <TableCell>{team.max_teammates}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{team.task_allocation_strategy}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={team.status === 'active' ? 'default' : 'secondary'}>
                      {team.status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={visible} onOpenChange={setVisible}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>
              <Typography variant="h6">Create Team</Typography>
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="team-name">Team Name</Label>
              <Input
                id="team-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Core Delivery Team"
              />
              {errors.name && <p className="text-sm text-destructive">{errors.name}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="team-description">Description</Label>
              <Input
                id="team-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
              />
            </div>
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
              <Select value={strategy} onValueChange={(value) => setStrategy(value as typeof strategy)}>
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
          <DialogFooter>
            <Button variant="outline" onClick={() => setVisible(false)}>
              Cancel
            </Button>
            <Button onClick={() => void createTeam()}>
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
};

export default TeamsPage;
