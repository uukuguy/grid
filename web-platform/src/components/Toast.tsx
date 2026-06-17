import { useEffect } from "react";
import { useAtom, useSetAtom } from "jotai";
import { CheckCircle, XCircle, AlertTriangle, Info, X } from "lucide-react";
import { toastsAtom, removeToastAtom, type Toast } from "../atoms/ui";
import { cn } from "../lib/utils";

const ICON_MAP = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
} as const;

const STYLE_MAP = {
  success: "border-green-500 bg-green-50 text-green-800",
  error: "border-red-500 bg-red-50 text-red-800",
  warning: "border-amber-500 bg-amber-50 text-amber-800",
  info: "border-blue-500 bg-blue-50 text-blue-800",
} as const;

function ToastItem({ toast }: { toast: Toast }) {
  const remove = useSetAtom(removeToastAtom);
  const Icon = ICON_MAP[toast.type];

  useEffect(() => {
    const timer = setTimeout(() => remove(toast.id), toast.duration ?? 5000);
    return () => clearTimeout(timer);
  }, [toast.id, toast.duration, remove]);

  return (
    <div
      className={cn("pointer-events-auto flex w-80 items-start gap-3 rounded-lg border p-3 shadow-lg", STYLE_MAP[toast.type])}
      role="alert"
    >
      <Icon className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="min-w-0 flex-1">
        {toast.title && <p className="text-sm font-medium">{toast.title}</p>}
        <p className="text-sm opacity-90">{toast.message}</p>
      </div>
      <button onClick={() => remove(toast.id)} className="shrink-0 rounded p-0.5 opacity-60 hover:opacity-100">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function ToastContainer() {
  const [toasts] = useAtom(toastsAtom);
  if (toasts.length === 0) return null;
  return (
    <div className="pointer-events-none fixed right-4 top-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => <ToastItem key={t.id} toast={t} />)}
    </div>
  );
}
