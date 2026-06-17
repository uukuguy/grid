import { ReactNode } from "react";
import { Inbox } from "lucide-react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-gray-300 mb-4">
        {icon || <Inbox className="w-12 h-12" />}
      </div>
      <h3 className="text-lg font-medium text-gray-600 mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-gray-400 max-w-sm mb-4">{description}</p>
      )}
      {action}
    </div>
  );
}
