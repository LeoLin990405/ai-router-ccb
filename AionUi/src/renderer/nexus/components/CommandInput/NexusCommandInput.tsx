/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { TerminalSquare } from 'lucide-react';
import React, { useState } from 'react';

interface NexusCommandInputProps {
  onSubmit?: (value: string) => void;
}

const NexusCommandInput: React.FC<NexusCommandInputProps> = ({ onSubmit }) => {
  const [value, setValue] = useState('');

  return (
    <div className='nexus-command-shell'>
      <TerminalSquare size={13} className='text-[var(--nexus-text-secondary)]' />
      <span className='nexus-command-prefix'>command</span>
      <input
        className='nexus-command-input'
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder='输入 /provider /model /context /task ...'
        onKeyDown={(event) => {
          if (event.key === 'Enter' && value.trim()) {
            onSubmit?.(value.trim());
            setValue('');
          }
        }}
      />
      <span className='nexus-command-shortcut'>↵</span>
    </div>
  );
};

export default NexusCommandInput;
