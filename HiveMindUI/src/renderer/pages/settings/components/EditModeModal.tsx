import type { IProvider } from '@/common/storage';
import ModalHOC from '@/renderer/utils/ModalHOC';
import { Input } from '@/renderer/components/ui/input';
import { Label } from '@/renderer/components/ui/label';
import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { LinkCloud } from '@icon-park/react';

// Provider Logo imports
import GeminiLogo from '@/renderer/assets/logos/gemini.svg';
import OpenAILogo from '@/renderer/assets/logos/openai.svg';
import AnthropicLogo from '@/renderer/assets/logos/anthropic.svg';
import OpenRouterLogo from '@/renderer/assets/logos/openrouter.svg';
import SiliconFlowLogo from '@/renderer/assets/logos/siliconflow.svg';
import QwenLogo from '@/renderer/assets/logos/qwen.svg';
import KimiLogo from '@/renderer/assets/logos/kimi.svg';
import ZhipuLogo from '@/renderer/assets/logos/zhipu.svg';
import XaiLogo from '@/renderer/assets/logos/xai.svg';
import VolcengineLogo from '@/renderer/assets/logos/volcengine.svg';
import BaiduLogo from '@/renderer/assets/logos/baidu.svg';
import TencentLogo from '@/renderer/assets/logos/tencent.svg';
import LingyiLogo from '@/renderer/assets/logos/lingyiwanwu.svg';
import PoeLogo from '@/renderer/assets/logos/poe.svg';
import ModelScopeLogo from '@/renderer/assets/logos/modelscope.svg';
import InfiniAILogo from '@/renderer/assets/logos/infiniai.svg';
import CtyunLogo from '@/renderer/assets/logos/ctyun.svg';
import StepFunLogo from '@/renderer/assets/logos/stepfun.svg';
import NewApiLogo from '@/renderer/assets/logos/newapi.svg';

/**
 * 供应商配置（包含名称、URL、Logo）
 * Provider config (includes name, URL, logo)
 */
const PROVIDER_CONFIGS = [
  { name: 'Gemini', url: '', logo: GeminiLogo, platform: 'gemini' },
  { name: 'Gemini (Vertex AI)', url: '', logo: GeminiLogo, platform: 'gemini-vertex-ai' },
  { name: 'New API', url: '', logo: NewApiLogo, platform: 'new-api' },
  { name: 'OpenAI', url: 'https://api.openai.com/v1', logo: OpenAILogo },
  { name: 'Anthropic', url: 'https://api.anthropic.com/v1', logo: AnthropicLogo },
  { name: 'OpenRouter', url: 'https://openrouter.ai/api/v1', logo: OpenRouterLogo },
  { name: 'SiliconFlow', url: 'https://api.siliconflow.cn/v1', logo: SiliconFlowLogo },
  { name: 'Dashscope', url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', logo: QwenLogo },
  { name: 'Moonshot (China)', url: 'https://api.moonshot.cn/v1', logo: KimiLogo },
  { name: 'Moonshot (Global)', url: 'https://api.moonshot.ai/v1', logo: KimiLogo },
  { name: 'Zhipu', url: 'https://open.bigmodel.cn/api/paas/v4', logo: ZhipuLogo },
  { name: 'xAI', url: 'https://api.x.ai/v1', logo: XaiLogo },
  { name: 'Ark', url: 'https://ark.cn-beijing.volces.com/api/v3', logo: VolcengineLogo },
  { name: 'Qianfan', url: 'https://qianfan.baidubce.com/v2', logo: BaiduLogo },
  { name: 'Hunyuan', url: 'https://api.hunyuan.cloud.tencent.com/v1', logo: TencentLogo },
  { name: 'Lingyi', url: 'https://api.lingyiwanwu.com/v1', logo: LingyiLogo },
  { name: 'Poe', url: 'https://api.poe.com/v1', logo: PoeLogo },
  { name: 'ModelScope', url: 'https://api-inference.modelscope.cn/v1', logo: ModelScopeLogo },
  { name: 'InfiniAI', url: 'https://cloud.infini-ai.com/maas/v1', logo: InfiniAILogo },
  { name: 'Ctyun', url: 'https://wishub-x1.ctyun.cn/v1', logo: CtyunLogo },
  { name: 'StepFun', url: 'https://api.stepfun.com/v1', logo: StepFunLogo },
];

/**
 * 根据名称或 URL 获取供应商 Logo
 * Get provider logo by name or URL
 */
const getProviderLogo = (name?: string, baseUrl?: string, platform?: string): string | null => {
  if (!name && !baseUrl && !platform) return null;

  // 优先按 platform 匹配（Gemini 系列）
  if (platform) {
    const byPlatform = PROVIDER_CONFIGS.find((p) => p.platform === platform);
    if (byPlatform) return byPlatform.logo;
  }

  // 按名称精确匹配
  const byName = PROVIDER_CONFIGS.find((p) => p.name === name);
  if (byName) return byName.logo;

  // 按名称模糊匹配（忽略大小写）
  const byNameLower = PROVIDER_CONFIGS.find((p) => p.name.toLowerCase() === name?.toLowerCase());
  if (byNameLower) return byNameLower.logo;

  // 按 URL 匹配
  if (baseUrl) {
    const byUrl = PROVIDER_CONFIGS.find((p) => p.url && baseUrl.includes(p.url.replace('https://', '').split('/')[0]));
    if (byUrl) return byUrl.logo;
  }

  return null;
};

/**
 * 供应商 Logo 组件
 * Provider Logo Component
 */
const ProviderLogo: React.FC<{ logo: string | null; name: string; size?: number }> = ({ logo, name, size = 20 }) => {
  if (logo) {
    return <img src={logo} alt={name} className='object-contain shrink-0' style={{ width: size, height: size }} />;
  }
  return <LinkCloud theme='outline' size={size} className='text-t-secondary flex shrink-0' />;
};

interface EditModeModalProps {
  visible: boolean;
  data?: IProvider;
  onChange(data: IProvider): void;
  onCancel(): void;
}

const EditModeModal: React.FC<EditModeModalProps> = ({ visible, data, onChange, onCancel }) => {
  const { t } = useTranslation();

  // Form state
  const [name, setName] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');

  // 获取供应商 Logo / Get provider logo
  const providerLogo = useMemo(() => {
    return getProviderLogo(data?.name, data?.baseUrl, data?.platform);
  }, [data?.name, data?.baseUrl, data?.platform]);

  useEffect(() => {
    if (data) {
      setName(data.name || '');
      setBaseUrl(data.baseUrl || '');
      setApiKey(data.apiKey || '');
    }
  }, [data, visible]);

  const handleSubmit = () => {
    if (!data || !name || !apiKey) return;
    onChange({ ...data, name, baseUrl, apiKey });
  };

  if (!visible) return null;

  const isBaseUrlRequired = data?.platform !== 'gemini' && data?.platform !== 'gemini-vertex-ai';

  return (
    <div className='fixed inset-0 z-50 flex items-center justify-center bg-black/50'>
      <div className='bg-background rounded-lg shadow-lg w-full max-w-md max-h-[90vh] overflow-auto'>
        <div className='flex items-center justify-between p-4 border-b'>
          <h2 className='text-lg font-semibold'>{t('settings.editModel')}</h2>
          <button onClick={onCancel} className='text-muted-foreground hover:text-foreground'>
            ✕
          </button>
        </div>

        <div className='p-6 space-y-4'>
          {/* 模型供应商名称（可编辑，带 Logo）/ Model Provider name (editable, with Logo) */}
          <div className='space-y-2'>
            <Label className='flex items-center gap-1.5'>
              <ProviderLogo logo={providerLogo} name={data?.name || ''} size={16} />
              <span>{t('settings.modelProvider')}</span>
              <span className='text-destructive'>*</span>
            </Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder={t('settings.modelProvider')} required />
          </div>

          {/* Base URL */}
          <div className='space-y-2'>
            <Label>
              {t('settings.baseUrl')}
              {isBaseUrlRequired && <span className='text-destructive ml-0.5'>*</span>}
            </Label>
            <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} disabled={data?.platform === 'gemini' || data?.platform === 'gemini-vertex-ai'} required={isBaseUrlRequired} />
          </div>

          {/* API Key */}
          <div className='space-y-2'>
            <Label>
              {t('settings.apiKey')}
              <span className='text-destructive ml-0.5'>*</span>
            </Label>
            <textarea value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={t('settings.apiKeyPlaceholder')} rows={4} className='w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2' required />
            <p className='text-xs text-muted-foreground'>💡 {t('settings.multiApiKeyEditTip')}</p>
          </div>
        </div>

        <div className='flex justify-end gap-2 p-4 border-t'>
          <button onClick={onCancel} className='px-4 py-2 rounded-md border hover:bg-accent'>
            {t('common.cancel')}
          </button>
          <button onClick={handleSubmit} disabled={!name || !apiKey} className='px-4 py-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50'>
            {t('common.save')}
          </button>
        </div>
      </div>
    </div>
  );
};

// 使用 ModalHOC 包装
const EditModeModalWithHOC = ModalHOC<{ data?: IProvider; onChange(data: IProvider): void }>(({ modalProps, modalCtrl, ...props }) => {
  return <EditModeModal visible={modalProps.visible} data={props.data} onChange={props.onChange} onCancel={modalCtrl.close} />;
});

export default EditModeModalWithHOC;
