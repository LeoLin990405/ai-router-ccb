/**
 * @license
 * Copyright 2026 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect } from 'react';
import Router from '@/renderer/router';
import NexusLayout from '../layouts/NexusLayout';
import NexusSidebar from '../components/Sidebar/NexusSidebar';

const NexusApp: React.FC = () => {
  useEffect(() => {
    document.body.classList.add('nexus-mode');
    return () => {
      document.body.classList.remove('nexus-mode');
    };
  }, []);

  return <Router layout={<NexusLayout sider={<NexusSidebar />} />} />;
};

export default NexusApp;
