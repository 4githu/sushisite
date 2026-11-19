import type { Snippet } from 'svelte';
export type MemoBridge = { day: string; modalOpen: boolean; render?: Snippet<[boolean]> };
