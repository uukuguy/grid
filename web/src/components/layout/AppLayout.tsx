import type { ReactNode } from "react";
import { useAtomValue } from "jotai";
import { NavRail } from "./NavRail";
import { TabBar } from "./TabBar";
import { SessionBar } from "@/components/SessionBar";
import { SessionControls } from "@/components/SessionControls";
import { ConnectionStatus } from "@/components/ConnectionStatus";
import { activeTabAtom } from "@/atoms/ui";

export function AppLayout({ children }: { children: ReactNode }) {
  const activeTab = useAtomValue(activeTabAtom);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      <NavRail />
      <div className="flex flex-1 flex-col">
        <TabBar />
        {activeTab === "chat" && <SessionBar />}
        <main className="flex flex-1 flex-col overflow-hidden">{children}</main>
      </div>
      {/* SessionControls is mounted globally (REQ-WEB-03, D-02) — visible
          on every tab, not just chat. Stop/Resume + live indicator are
          always available. */}
      <div className="pointer-events-none fixed right-4 bottom-4 z-40">
        <div className="pointer-events-auto flex items-center gap-3">
          <ConnectionStatus />
          <SessionControls />
        </div>
      </div>
    </div>
  );
}