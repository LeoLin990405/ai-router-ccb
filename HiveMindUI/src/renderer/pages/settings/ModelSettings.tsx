import React, { useEffect, useMemo, useState } from 'react';
import { ipcBridge } from '@/common';
import ModelSelector from '@/renderer/components/ModelSelector';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/renderer/components/ui/card';
import { Button } from '@/renderer/components/ui/button';
import { RefreshCcw } from 'lucide-react';
import type { AcpBackendAll, ModelConfig, UserModelPreferences } from '@/types/acpTypes';
import { useTranslation } from 'react-i18next';

const PROVIDERS: Array<{ id: AcpBackendAll; name: string; icon: string }> = [
  { id: 'claude', name: 'Claude', icon: '🤖' },
  { id: 'codex', name: 'Codex', icon: '🔮' },
  { id: 'gemini', name: 'Gemini', icon: '💎' },
  { id: 'qwen', name: 'Qwen', icon: '🐼' },
  { id: 'kimi', name: 'Kimi', icon: '🌙' },
  { id: 'iflow', name: 'iFlow', icon: '⚡' },
  { id: 'ollama', name: 'Ollama', icon: '🦙' },
  { id: 'opencode', name: 'OpenCode', icon: '📦' },
  { id: 'goose', name: 'Goose', icon: '🪿' },
  { id: 'auggie', name: 'Auggie', icon: '🧩' },
  { id: 'copilot', name: 'Copilot', icon: '🐙' },
  { id: 'qoder', name: 'Qoder', icon: '🧠' },
  { id: 'openclaw-gateway', name: 'OpenClaw', icon: '🦀' },
  { id: 'custom', name: 'Custom', icon: '🛠️' },
];

const ModelSettings: React.FC = () => {
  const { t } = useTranslation();
  const [preferences, setPreferences] = useState<UserModelPreferences>({ selectedModels: {} });
  const [ollamaModels, setOllamaModels] = useState<ModelConfig[]>([]);
  const [refreshingOllama, setRefreshingOllama] = useState(false);

  useEffect(() => {
    const loadPreferences = async () => {
      try {
        const prefs = await ipcBridge.models.getUserPreferences.invoke();
        setPreferences({ selectedModels: prefs.selectedModels || {}, lastUpdated: prefs.lastUpdated });
      } catch (error) {
        console.error('Failed to load model preferences:', error);
      }
    };

    void loadPreferences();
    void refreshOllamaModels();
  }, []);

  const refreshOllamaModels = async () => {
    setRefreshingOllama(true);
    try {
      const models = await ipcBridge.models.getOllamaModels.invoke();
      setOllamaModels(models);
    } catch (error) {
      console.error('Failed to refresh Ollama models:', error);
    } finally {
      setRefreshingOllama(false);
    }
  };

  const handleModelChange = async (provider: AcpBackendAll, modelId: string) => {
    const nextPreferences: UserModelPreferences = {
      selectedModels: {
        ...preferences.selectedModels,
        [provider]: modelId,
      },
    };

    setPreferences(nextPreferences);

    try {
      await ipcBridge.models.saveUserPreferences.invoke(nextPreferences);
    } catch (error) {
      console.error('Failed to save model preferences:', error);
    }
  };

  const updatedAtText = useMemo(() => {
    if (!preferences.lastUpdated) return null;
    const date = new Date(preferences.lastUpdated);
    if (Number.isNaN(date.getTime())) return null;
    return date.toLocaleString();
  }, [preferences.lastUpdated]);

  return (
    <div className='hive-model-settings mb-20px'>
      <div className='hive-model-settings__header'>
        <div>
          <h2 className='text-18px font-semibold text-t-primary m-0'>{t('settings.model', { defaultValue: 'Model Preferences' })}</h2>
          <p className='text-13px text-t-secondary mt-6px mb-0'>{t('settings.modelDescription', { defaultValue: 'Choose a default model for each provider.' })}</p>
          {updatedAtText && <p className='text-12px text-t-tertiary mt-6px mb-0'>Last updated: {updatedAtText}</p>}
        </div>
      </div>

      <div className='hive-model-settings__grid'>
        {PROVIDERS.map((provider) => (
          <Card key={provider.id} className='hive-agent-surface'>
            <CardHeader className='pb-3'>
              <CardTitle className='flex items-center gap-2 text-15px'>
                <span className='text-18px'>{provider.icon}</span>
                <span>{provider.name}</span>
              </CardTitle>
              <CardDescription>{t(`settings.${provider.id}ModelDescription`, { defaultValue: `Default model for ${provider.name}` })}</CardDescription>
            </CardHeader>
            <CardContent className='pt-0'>
              <div className='flex items-center gap-2'>
                <ModelSelector provider={provider.id} value={preferences.selectedModels?.[provider.id]} onChange={(modelId) => void handleModelChange(provider.id, modelId)} className='flex-1' />
                {provider.id === 'ollama' && (
                  <Button variant='outline' size='icon' onClick={() => void refreshOllamaModels()} disabled={refreshingOllama}>
                    <RefreshCcw className={refreshingOllama ? 'animate-spin' : ''} size={15} />
                  </Button>
                )}
              </div>
              {provider.id === 'ollama' && ollamaModels.length > 0 && <p className='text-11px text-t-secondary mt-8px mb-0'>{ollamaModels.length} models detected</p>}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
};

export default ModelSettings;
