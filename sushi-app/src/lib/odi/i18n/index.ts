import { writable } from 'svelte/store';

export type Locale = 'ko' | 'en';
export const translations = {
  ko: { language: '언어', newSession: '새 세션', home: '홈', templates: '템플릿', reports: '리포트', practice: '내 연습', signIn: '로그인', signInHint: '로그인이 필요해요', user: '사용자', level: '새싹 보이스', closeSidebar: '사이드바 접기', openSidebar: '사이드바 열기', closeMenu: '메뉴 닫기' },
  en: { language: 'Language', newSession: 'New session', home: 'Home', templates: 'Templates', reports: 'Reports', practice: 'My practice', signIn: 'Sign in', signInHint: 'Sign in to get started', user: 'User', level: 'Sprout Voice', closeSidebar: 'Collapse sidebar', openSidebar: 'Open sidebar', closeMenu: 'Close menu' }
} as const;
export type MessageKey = keyof typeof translations.ko;
const localeStore = writable<Locale>('ko');
let activeLocale: Locale = 'ko';
let overrides: Record<string, string> = {};
let listening = false;
function refreshSubscribers() {
  localeStore.set(activeLocale === 'ko' ? 'en' : 'ko');
  localeStore.set(activeLocale);
}
export async function refreshTranslations() {
  if (typeof window === 'undefined') return;
  try {
    const response = await fetch('/rehear-translations', { cache: 'no-store' });
    if (!response.ok) return;
    const data = await response.json();
    overrides = data.overrides || {};
    refreshSubscribers();
  } catch { /* Keep bundled copy if the network is unavailable. */ }
}

export const locale = { subscribe: localeStore.subscribe };
export function setLocale(value: Locale) {
  activeLocale = value;
  localeStore.set(value);
  if (typeof window !== 'undefined') {
    localStorage.setItem('rehear.locale', value);
    document.documentElement.lang = value;
  }
}
export function initLocale() {
  if (typeof window === 'undefined') return;
  const saved = localStorage.getItem('rehear.locale');
  if (new URLSearchParams(window.location.search).get('review_preview') === 'en') {
    activeLocale = 'en';
    localeStore.set('en');
    document.documentElement.lang = 'en';
  } else setLocale(saved === 'en' ? 'en' : 'ko');
  void refreshTranslations();
  if (!listening) {
    listening = true;
    window.addEventListener('focus', refreshTranslations);
    if ('BroadcastChannel' in window) {
      const channel = new BroadcastChannel('rehear-translation-updates');
      channel.addEventListener('message', refreshTranslations);
    }
  }
}
export function message(language: Locale, key: MessageKey): string { return language === "en" ? overrides[`nav:${key}`] ?? translations.en[key] : translations.ko[key]; }

import englishCopy from './copy.json';
/** Source text remains the Korean fallback; translations are editable in copy.json. */
export function copy(language: Locale, korean: string): string {
  return language === 'en' ? overrides[`copy:${korean}`] ?? (englishCopy as Record<string, string>)[korean] ?? korean : korean;
}

export function duration(language: Locale, seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(s / 60), rest = s % 60;
  return language === 'en' ? `${minutes} min ${rest} sec` : `${minutes}분 ${rest}초`;
}
