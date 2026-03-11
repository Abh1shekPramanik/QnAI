import React, { useEffect, useRef, useState } from "react";
import { Mic, RefreshCcw } from "lucide-react";
import axios from "axios";

const BACKEND_URL = "https://0416-131-239-113-82.ngrok-free.app";

export default function TranscriptWindow({ incomingTranscript, sessionId }) {
  const scrollRef = useRef(null);
  const [transcripts, setTranscripts] = useState([]);

  // 1. Initial Load from Database
  useEffect(() => {
    if (sessionId) {
      axios.get(`${BACKEND_URL}/api/sessions/${sessionId}/history`)
        .then(res => {
          const hist = Array.isArray(res.data.transcripts) ? res.data.transcripts : [];
          setTranscripts(hist.map(t => ({ ...t, is_final: true })));
        })
        .catch(err => console.error("History fetch failed:", err));
    }
  }, [sessionId]);

  // 2. Handle Live WebSocket Messages
  useEffect(() => {
    if (!incomingTranscript) return;

    setTranscripts(prev => {
      // Find if this ID already exists in our current window
      const idx = prev.findIndex(t => t.id === incomingTranscript.id);
      
      if (idx !== -1) {
        // Update the existing sentence (this handles partial words filling in)
        const updated = [...prev];
        updated[idx] = { ...updated[idx], ...incomingTranscript };
        return updated;
      } else {
        // This is a brand new sentence ID, append it to the end of the history
        return [...prev, incomingTranscript];
      }
    });
  }, [incomingTranscript]);

  // 3. Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcripts]);

  const forceSync = async () => {
    try {
      const res = await axios.get(`${BACKEND_URL}/api/sessions/${sessionId}/history`);
      const hist = Array.isArray(res.data.transcripts) ? res.data.transcripts : [];
      setTranscripts(hist.map(t => ({ ...t, is_final: true })));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="card" style={{height: "100%", display: "flex", flexDirection: "column"}}>
      <div style={{display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem"}}>
        <div style={{display: "flex", alignItems: "center"}}>
          <Mic size={18} style={{marginRight: 8, color: "#2563eb"}} />
          <h3 style={{margin: 0}}>Lecture Transcript</h3>
        </div>
        <button onClick={forceSync} title="Sync with Server" style={{background: "none", border: "none", cursor: "pointer", color: "#94a3b8"}}>
          <RefreshCcw size={16} />
        </button>
      </div>

      <div className="transcript-area" ref={scrollRef} style={{flex: 1, overflowY: "auto"}}>
        {transcripts.length === 0 ? (
          <p style={{color: "#94a3b8", textAlign: "center", marginTop: "2rem"}}>Bot is joined and listening...</p>
        ) : (
          transcripts.map((t, i) => (
            <div key={t.id || i} className="transcript-item" style={{marginBottom: "1rem"}}>
              <span className="speaker" style={{fontWeight: "bold", color: "#2563eb", marginRight: "0.5rem"}}>
                {t.speaker}:
              </span> 
              <span style={{color: "#1e293b"}}>
                {t.text}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
