import { useState, useEffect, useRef } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Issue #8 — Topic Setter
 * Lets the professor type and update the current lecture topic.
 * The topic is persisted via FastAPI and consumed by:
 *   - SessionContext (Issue #3) for cross-view sync
 *   - Gemini calls (Issues #4, #6) as context
 */
export default function TopicSetter() {
  const [topic, setTopic] = useState("");
  const [savedTopic, setSavedTopic] = useState("");
  const [updatedAt, setUpdatedAt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  // Fetch the current topic on mount
  useEffect(() => {
    fetchTopic();
  }, []);

  async function fetchTopic() {
    try {
      const res = await fetch(`${API_BASE}/api/topic/`);
      if (res.status === 404) return; // no topic set yet
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setTopic(data.topic);
      setSavedTopic(data.topic);
      setUpdatedAt(data.updated_at);
    } catch (err) {
      console.error("Failed to fetch topic:", err);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmed = topic.trim();
    if (!trimmed || trimmed === savedTopic) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/topic/`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: trimmed }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setSavedTopic(data.topic);
      setUpdatedAt(data.updated_at);
    } catch (err) {
      setError("Failed to update topic. Please try again.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function handleClear() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/topic/`, { method: "DELETE" });
      if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
      setTopic("");
      setSavedTopic("");
      setUpdatedAt("");
      inputRef.current?.focus();
    } catch (err) {
      setError("Failed to clear topic.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const hasUnsavedChanges = topic.trim() !== savedTopic;
  const formattedTime = updatedAt
    ? new Date(updatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : null;

  return (
    <div className="w-full max-w-xl mx-auto">
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <input
          ref={inputRef}
          type="text"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Enter current lecture topic…"
          maxLength={300}
          disabled={loading}
          className="flex-1 px-4 py-2 rounded-lg border border-gray-300 
                     focus:outline-none focus:ring-2 focus:ring-blue-500 
                     disabled:opacity-50 text-sm"
        />
        <button
          type="submit"
          disabled={loading || !hasUnsavedChanges}
          className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium
                     hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors"
        >
          {loading ? "Saving…" : "Set Topic"}
        </button>
        {savedTopic && (
          <button
            type="button"
            onClick={handleClear}
            disabled={loading}
            className="px-3 py-2 rounded-lg border border-gray-300 text-gray-600 text-sm
                       hover:bg-gray-100 disabled:opacity-40 transition-colors"
          >
            Clear
          </button>
        )}
      </form>

      {/* Status line */}
      <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
        <span>
          {savedTopic
            ? `Current topic: "${savedTopic}"`
            : "No topic set — students will see a generic context."}
        </span>
        {formattedTime && <span>Updated at {formattedTime}</span>}
      </div>

      {error && (
        <p className="mt-2 text-xs text-red-600">{error}</p>
      )}
    </div>
  );
}
