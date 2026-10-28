import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { chinese } from './translations';

export type Locale = 'en' | 'zh-CN';
const storageKey = 'geek-mind-language';
type Language = { locale: Locale; setLocale: (locale: Locale) => void; t: (text: string) => string };
const LanguageContext = createContext<Language | null>(null);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => {
    try { return localStorage.getItem(storageKey) === 'zh-CN' ? 'zh-CN' : 'en'; }
    catch { return 'en'; }
  });
  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = locale === 'zh-CN'
      ? 'Geek Mind — 一个智能体运行时，多种具身形态。'
      : 'Geek Mind — One Agent Runtime. Multiple Embodiments.';
    document.querySelector('meta[name="description"]')?.setAttribute('content', locale === 'zh-CN'
      ? 'Geek Mind 通过共享的具身智能体运行时，连接多模态感知、任务规划与物理执行，适配 Unitree Go2 和 ARX X5。'
      : 'Geek Mind connects multimodal perception, task planning, and physical execution across Unitree Go2 and ARX X5 through a shared embodied-agent runtime.');
    try { localStorage.setItem(storageKey, locale); } catch { /* Switching still works when storage is unavailable. */ }
  }, [locale]);
  const value = useMemo(() => ({ locale, setLocale, t: (text: string) => locale === 'zh-CN' ? chinese[text] ?? text : text }), [locale]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const language = useContext(LanguageContext);
  if (!language) throw new Error('LanguageProvider is required');
  return language;
}

export function LanguageSwitch() {
  const { locale, setLocale, t } = useLanguage();
  return <div className="language-switch" role="group" aria-label={t('Language')}>
    <button type="button" lang="zh-CN" aria-label="切换为中文" aria-pressed={locale === 'zh-CN'} onClick={() => setLocale('zh-CN')}>CN</button>
    <span aria-hidden="true">/</span>
    <button type="button" lang="en" aria-label="Switch to English" aria-pressed={locale === 'en'} onClick={() => setLocale('en')}>EN</button>
  </div>;
}
