import { writable } from 'svelte/store';

export const toast = writable<string | null>(null);
let timer: ReturnType<typeof setTimeout> | null = null;

export function showToast(message: string) {
  toast.set(message);
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => toast.set(null), 4200);
}
