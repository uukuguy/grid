import { useAtom, useSetAtom } from "jotai";
import { useEffect, useCallback } from "react";
import {
  collaborationStatusAtom,
  collaborationAgentsAtom,
  collaborationProposalsAtom,
  collaborationEventsAtom,
  collaborationSharedStateAtom,
  collaborationLoadingAtom,
} from "@/atoms/collaboration";
import {
  collaborationClient,
  type CollaborationAgent,
  type CollaborationEvent,
  type CollaborationStatus,
  type Proposal,
  type SharedStateEntry,
} from "../api/collaboration";
import { AgentList } from "@/components/collaboration/AgentList";
import { EventLog } from "@/components/collaboration/EventLog";
import { ProposalList } from "@/components/collaboration/ProposalList";
import { SharedState } from "@/components/collaboration/SharedState";

export default function Collaboration() {
  const [status] = useAtom(collaborationStatusAtom);
  const [loading] = useAtom(collaborationLoadingAtom);
  const setStatus = useSetAtom(collaborationStatusAtom);
  const setAgents = useSetAtom(collaborationAgentsAtom);
  const setProposals = useSetAtom(collaborationProposalsAtom);
  const setEvents = useSetAtom(collaborationEventsAtom);
  const setSharedState = useSetAtom(collaborationSharedStateAtom);
  const setLoading = useSetAtom(collaborationLoadingAtom);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      // OBSTACK Phase E.4 commit 2/2 — all 5 endpoints routed
      // through the shared collaborationClient (same surface as
      // the Python ``CollaborationClient``). The Promise.all
      // shape mirrors the legacy UI — the client handles the
      // Bearer header per request and the dict/array wire
      // shapes are preserved by the client's passthrough bypass.
      const [
        statusRes,
        agentsRes,
        proposalsRes,
        eventsRes,
        stateRes,
      ] = await Promise.all([
        collaborationClient.get_status() as Promise<CollaborationStatus>,
        collaborationClient.list_agents() as Promise<CollaborationAgent[]>,
        collaborationClient.list_proposals() as Promise<Proposal[]>,
        collaborationClient.list_events() as Promise<CollaborationEvent[]>,
        collaborationClient.get_shared_state() as Promise<{ entries?: SharedStateEntry[] }>,
      ]);
      setStatus(statusRes);
      setAgents(agentsRes);
      setProposals(proposalsRes);
      // Legacy unwrap: server uses ``#[serde(flatten)] event: Value``
      // so each event in ``list_events`` carries every field at the
      // top level. The Python client preserves the dict verbatim
      // (CollaborationEvent.event) so callers can do the same
      // ``e.event ?? e`` unwrap the UI has always done.
      setEvents(
        eventsRes.map((e: CollaborationEvent) => (e.event ?? (e as unknown as Record<string, unknown>))),
      );
      setSharedState(Array.isArray(stateRes.entries) ? stateRes.entries : []);
    } catch {
      // Silently handle — endpoints may not be available yet
    } finally {
      setLoading(false);
    }
  }, [setStatus, setAgents, setProposals, setEvents, setSharedState, setLoading]);

  // Fetch on mount and poll every 5s
  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <div className="flex flex-1 flex-col overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border">
        <div>
          <h2 className="text-sm font-medium">Agent Collaboration</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Multi-agent collaboration state, proposals, and shared context.
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="text-xs px-3 py-1 rounded bg-secondary text-muted-foreground hover:text-foreground disabled:opacity-50 transition-colors"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {/* Status summary */}
      {status && (
        <div className="px-4 py-2 border-b border-border">
          <div className="grid grid-cols-4 gap-4 text-xs">
            <div>
              <span className="text-muted-foreground">Agents:</span>{" "}
              <span className="font-mono">{status.agent_count}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Active:</span>{" "}
              <span className="font-mono">{status.active_agent ?? "none"}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Pending:</span>{" "}
              <span className="font-mono">{status.pending_proposals}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Events:</span>{" "}
              <span className="font-mono">{status.event_count}</span>
            </div>
          </div>
        </div>
      )}

      {/* Four panels in a 2x2 grid */}
      <div className="flex-1 grid grid-cols-2 gap-0 overflow-auto">
        {/* Agents */}
        <div className="border-r border-b border-border p-3 overflow-auto">
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
            Agents
          </h3>
          <AgentList />
        </div>

        {/* Proposals */}
        <div className="border-b border-border p-3 overflow-auto">
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
            Proposals
          </h3>
          <ProposalList />
        </div>

        {/* Event Log */}
        <div className="border-r border-border p-3 overflow-auto">
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
            Event Timeline
          </h3>
          <EventLog />
        </div>

        {/* Shared State */}
        <div className="p-3 overflow-auto">
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
            Shared State
          </h3>
          <SharedState />
        </div>
      </div>
    </div>
  );
}
