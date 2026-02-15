/**
 * @license
 * Copyright 2025 HiveMind (hivemind.com)
 * SPDX-License-Identifier: Apache-2.0
 */

import { ipcBridge } from '@/common';
import type { MenuItemConstructorOptions } from 'electron';
import { Menu } from 'electron';

export function setupApplicationMenu(): void {
  const isMac = process.platform === 'darwin';
  const appDisplayName = '蜂巢';

  const template: MenuItemConstructorOptions[] = [];

  if (isMac) {
    template.push({
      label: appDisplayName,
      submenu: [{ label: `关于${appDisplayName}`, role: 'about' }, { type: 'separator' }, { label: '服务', role: 'services' }, { type: 'separator' }, { label: `隐藏${appDisplayName}`, role: 'hide' }, { label: '隐藏其他', role: 'hideOthers' }, { label: '显示全部', role: 'unhide' }, { type: 'separator' }, { label: `退出${appDisplayName}`, role: 'quit' }],
    });
  }

  template.push({
    label: '文件',
    submenu: [{ label: '关闭', role: 'close' }, ...(!isMac ? ([{ type: 'separator' }, { label: '退出', role: 'quit' }] as MenuItemConstructorOptions[]) : [])],
  });

  template.push({
    label: '编辑',
    submenu: [
      { label: '撤销', role: 'undo' },
      { label: '重做', role: 'redo' },
      { type: 'separator' },
      { label: '剪切', role: 'cut' },
      { label: '复制', role: 'copy' },
      { label: '粘贴', role: 'paste' },
      ...(isMac
        ? ([
            { label: '粘贴并匹配样式', role: 'pasteAndMatchStyle' },
            { label: '删除', role: 'delete' },
            { label: '全选', role: 'selectAll' },
          ] as MenuItemConstructorOptions[])
        : ([{ label: '删除', role: 'delete' }, { type: 'separator' }, { label: '全选', role: 'selectAll' }] as MenuItemConstructorOptions[])),
    ],
  });

  template.push({
    label: '查看',
    submenu: [{ label: '重新加载', role: 'reload' }, { label: '强制重新加载', role: 'forceReload' }, { label: '开发者工具', role: 'toggleDevTools' }, { type: 'separator' }, { label: '重置缩放', role: 'resetZoom' }, { label: '放大', role: 'zoomIn' }, { label: '缩小', role: 'zoomOut' }, { type: 'separator' }, { label: '切换全屏', role: 'togglefullscreen' }],
  });

  template.push({
    label: '窗口',
    submenu: [{ label: '最小化', role: 'minimize' }, { label: '缩放', role: 'zoom' }, ...(isMac ? ([{ type: 'separator' }, { label: '前置全部窗口', role: 'front' }] as MenuItemConstructorOptions[]) : [])],
  });

  template.push({
    label: '帮助',
    submenu: [
      {
        label: '检查更新...',
        click: () => {
          ipcBridge.update.open.emit({ source: 'menu' });
        },
      },
    ],
  });

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}
