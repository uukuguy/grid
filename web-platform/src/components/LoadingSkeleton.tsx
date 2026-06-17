interface LoadingSkeletonProps {
  className?: string;
}

export function CardSkeleton({ className }: LoadingSkeletonProps) {
  return (
    <div className={`animate-pulse rounded-lg border p-4 ${className || ""}`}>
      <div className="h-4 bg-gray-200 rounded w-3/4 mb-3" />
      <div className="h-3 bg-gray-200 rounded w-1/2 mb-2" />
      <div className="h-3 bg-gray-200 rounded w-1/4" />
    </div>
  );
}

export function ListSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="animate-pulse flex items-center gap-3 p-4 rounded-lg border">
          <div className="h-10 w-10 bg-gray-200 rounded-full" />
          <div className="flex-1">
            <div className="h-4 bg-gray-200 rounded w-1/3 mb-2" />
            <div className="h-3 bg-gray-200 rounded w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function StatsSkeleton() {
  return (
    <div className="grid grid-cols-3 gap-4">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="animate-pulse rounded-lg border p-4">
          <div className="h-4 bg-gray-200 rounded w-16 mb-3" />
          <div className="h-8 bg-gray-200 rounded w-12" />
        </div>
      ))}
    </div>
  );
}
