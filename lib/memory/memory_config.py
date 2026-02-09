#!/usr/bin/env python3
"""
Memory Configuration Manager (Phase 4)

Runtime configuration management for the CCB memory system.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def _warn(message: str) -> None:
    sys.stderr.write(f"{message}\n")


class MemoryConfig:
    """Manages memory system configuration at runtime."""

    DEFAULT_CONFIG = {
        "enabled": True,
        "auto_inject": True,
        "auto_record": True,
        "max_injected_memories": 5,
        "inject_system_context": True,
        "injection_strategy": "recent_plus_relevant",  # "recent", "relevant", "recent_plus_relevant"
        "skills": {
            "auto_discover": True,
            "recommend_skills": True,
            "max_recommendations": 3
        },
        "recommendation": {
            "enabled": True,
            "auto_switch_provider": False,
            "confidence_threshold": 0.7
        },
        "consolidation": {
            "llm_enabled": False,
            "llm_provider": "kimi",
            "auto_consolidate": False,
            "consolidation_hours": 24
        }
    }

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.

        Args:
            config_path: Path to config file (default: ~/.ccb/memory_config.json)
        """
        self.config_path = config_path or Path.home() / ".ccb" / "memory_config.json"
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                _warn(f"[MemoryConfig] Error loading config: {e}")
                self._config = {}

        # Merge with defaults
        self._config = self._merge_with_defaults(self._config)

    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge config with default values."""
        result = self.DEFAULT_CONFIG.copy()

        for key, value in config.items():
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = {**result[key], **value}
                else:
                    result[key] = value
            else:
                result[key] = value

        return result

    def _save(self) -> None:
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
        except IOError as e:
            _warn(f"[MemoryConfig] Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Supports dot notation for nested keys: "skills.auto_discover"

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set configuration value.

        Supports dot notation for nested keys: "skills.auto_discover"

        Args:
            key: Configuration key
            value: Value to set
        """
        keys = key.split('.')

        if len(keys) == 1:
            self._config[key] = value
        else:
            # Navigate to nested location
            current = self._config
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                elif not isinstance(current[k], dict):
                    current[k] = {}
                current = current[k]
            current[keys[-1]] = value

        self._save()

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values.

        Returns:
            Full configuration dictionary
        """
        return self._config.copy()

    def update(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update multiple configuration values.

        Args:
            updates: Dictionary of updates

        Returns:
            Updated configuration
        """
        for key, value in updates.items():
            self.set(key, value)

        return self.get_all()

    def reset(self) -> Dict[str, Any]:
        """Reset configuration to defaults.

        Returns:
            Default configuration
        """
        self._config = self.DEFAULT_CONFIG.copy()
        self._save()
        return self._config

    def validate(self) -> Dict[str, Any]:
        """Validate current configuration.

        Returns:
            Validation result with errors list
        """
        errors = []

        # Validate max_injected_memories
        max_mem = self.get("max_injected_memories", 5)
        if not isinstance(max_mem, int) or max_mem < 0 or max_mem > 50:
            errors.append("max_injected_memories must be integer 0-50")

        # Validate injection_strategy
        strategy = self.get("injection_strategy", "recent_plus_relevant")
        valid_strategies = ["recent", "relevant", "recent_plus_relevant"]
        if strategy not in valid_strategies:
            errors.append(f"injection_strategy must be one of: {valid_strategies}")

        # Validate confidence_threshold
        threshold = self.get("recommendation.confidence_threshold", 0.7)
        if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
            errors.append("recommendation.confidence_threshold must be 0-1")

        # Validate max_recommendations
        max_rec = self.get("skills.max_recommendations", 3)
        if not isinstance(max_rec, int) or max_rec < 0 or max_rec > 10:
            errors.append("skills.max_recommendations must be integer 0-10")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "config": self._config
        }


# Global singleton instance
_config_instance: Optional[MemoryConfig] = None


def get_memory_config() -> MemoryConfig:
    """Get the global memory configuration instance.

    Returns:
        MemoryConfig singleton
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = MemoryConfig()
    return _config_instance
