import { atom } from "jotai";

// Sidebar collapsed
export const sidebarCollapsedAtom = atom<boolean>(false);

// Loading states
export const isLoadingAtom = atom<boolean>(false);

// Error message
export const errorAtom = atom<string | null>(null);

// Toast notifications
export type ToastType = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  title?: string;
  duration?: number;
}

export type AddToastInput = Omit<Toast, "id">;

export const toastsAtom = atom<Toast[]>([]);

export const addToastAtom = atom(null, (_get, set, input: AddToastInput) => {
  const toast: Toast = { ...input, id: crypto.randomUUID() };
  set(toastsAtom, [..._get(toastsAtom), toast]);
});

export const removeToastAtom = atom(null, (_get, set, id: string) => {
  set(toastsAtom, _get(toastsAtom).filter((t) => t.id !== id));
});
