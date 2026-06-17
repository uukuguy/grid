import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MessageSquare, Users, Bot, Inbox } from "lucide-react";
import { useAtom, useSetAtom } from "jotai";
import { sessionsAtom } from "../atoms";
import { sessionsApi } from "../api/sessions";
import { addToastAtom } from "../atoms/ui";
import { StatsCard } from "../components/dashboard/StatsCard";
import { RecentSessions } from "../components/dashboard/RecentSessions";
import { StatsSkeleton } from "../components/LoadingSkeleton";
import { EmptyState } from "../components/EmptyState";

export function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessions, setSessions] = useAtom(sessionsAtom);
  const addToast = useSetAtom(addToastAtom);
  const navigate = useNavigate();

  useEffect(() => {
    sessionsApi
      .list()
      .then(setSessions)
      .catch((err) => {
        const msg = err instanceof Error ? err.message : "Failed to load sessions";
        setError(msg);
        addToast({ type: "error", message: msg });
      })
      .finally(() => setLoading(false));
  }, [setSessions, addToast]);

  const handleNewChat = async () => {
    try {
      const session = await sessionsApi.create();
      navigate(`/chat/${session.id}`);
    } catch (err) {
      addToast({ type: "error", message: "Failed to create session" });
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
        <StatsSkeleton />
      </div>
    );
  }

  if (error && sessions.length === 0) {
    return (
      <div className="max-w-4xl mx-auto">
        <EmptyState icon={<Inbox className="w-12 h-12" />} title="Failed to load" description={error} />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatsCard title="Sessions" value={sessions.length} icon={<MessageSquare className="w-6 h-6" />} />
        <StatsCard title="Active" value={sessions.filter((s) => s.status === "active").length} icon={<Users className="w-6 h-6" />} />
        <StatsCard title="Agents" value={sessions.length} icon={<Bot className="w-6 h-6" />} />
      </div>

      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-3">Recent Sessions</h2>
        {sessions.length === 0 ? (
          <p className="text-gray-400 text-sm">No sessions yet. Start a new chat to get going.</p>
        ) : (
          <RecentSessions sessions={sessions} />
        )}
      </div>

      <button
        onClick={handleNewChat}
        className="w-full bg-primary text-white py-3 rounded-lg hover:opacity-90"
      >
        + New Chat
      </button>
    </div>
  );
}
