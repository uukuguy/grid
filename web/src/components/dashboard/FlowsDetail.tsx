// OBSTACK Phase C.0 — detail panel placeholder (commit C.3).
//
// Real timeline + summary + evaluation rendering lands in commit C.4.
// This file exists so FlowsPage can render the right-side panel without
// compile errors while C.3 ships.

interface FlowsDetailProps {
  businessKey: string;
  onClose: () => void;
}

export function FlowsDetail({ businessKey }: FlowsDetailProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="truncate font-mono text-sm font-semibold">{businessKey}</h2>
      </div>
      <p className="text-sm text-muted-foreground">
        Timeline / summary / evaluation detail lands in commit C.4.
      </p>
    </div>
  );
}
