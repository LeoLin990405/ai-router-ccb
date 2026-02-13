# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.10.0] - 2026-02-14

### Added

#### 🤖 Agent Teams - Multi-AI Collaboration Platform

- **Team Management**
  - Create and manage AI agent teams
  - Support for 5 task allocation strategies (round_robin, load_balance, skill_based, etc.)
  - Real-time team status monitoring
  - Team performance analytics

- **Task Management**
  - Drag-and-drop Kanban board (@dnd-kit)
  - 5 status columns: Pending, In Progress, Completed, Failed, Cancelled
  - Task priority system (P1-P10)
  - Task dependencies and blocking visualization
  - Cost tracking per task

- **AI Provider Integrations**
  - Claude (Anthropic)
  - Gemini (Google)
  - Kimi (Moonshot)
  - Qwen (Alibaba)
  - DeepSeek
  - CCB Gateway

- **Real-time Updates**
  - WebSocket-based live updates
  - Activity timeline
  - Toast notifications for task updates

- **Analytics & Visualization**
  - Cost analysis charts
  - Performance metrics
  - Dependency graphs
  - Task completion trends

- **UI Components (Phoenix Design System)**
  - Typography component with variants
  - StatCard with trend indicators
  - ActivityTimeline for real-time updates
  - PerformanceChart for data visualization
  - Design tokens (colors, spacing, radius, shadows)
  - 13 custom Agent Teams components

- **Performance Optimizations**
  - Virtual scrolling (@tanstack/react-virtual)
  - Debounced search
  - React.memo for component optimization
  - Framer Motion animations

- **Backend Services**
  - TaskManager for task lifecycle management
  - TeamCoordinator for team operations
  - MessageBroker for inter-agent communication
  - DependencyResolver for task dependencies
  - ProviderRouter for AI provider management
  - TaskExecutionRuntime for task execution
  - Complete database schema (6 tables)
  - 30+ IPC interfaces

- **Testing**
  - Backend unit tests (5 test suites)
  - Frontend component tests (5 test files)

- **Internationalization**
  - 6 language support (EN, ZH, TW, JP, KO, TR)

### Changed

- Updated React components to use Phoenix Design System
- Improved performance with virtual scrolling and memoization

### Dependencies

- Added @dnd-kit/core, @dnd-kit/sortable, @dnd-kit/utilities
- Added framer-motion
- Added recharts, d3
- Added zustand
- Added @tanstack/react-virtual
- Added clsx

## [1.9.0] - Previous Release

### Added
- Initial release features
