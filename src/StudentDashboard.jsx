import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { Send, MessageCircle, Mic, AlertCircle, HelpCircle } from "lucide-react";

const BACKEND_URL = "https://0416-131-239-113-82.ngrok-free.app";

export default function StudentDashboard() {
  const [sessionId, setSessionId] = useState("session-001");
  const [userName, setUserName] = useState("");
  const [userId, setUserId] = useState(null);
  const [question, setQuestion] = useState("");
  const [transcripts, setTranscripts] = useState([]);
  const [isJoined, setIsJoined] = useState(false);
  const ws = useRef(null);

  useEffect(() => {
    if (!isJoined) return;
    
    ws.current = new WebSocket(`${BACKEND_URL.replace("https", "wss")}/api/recall/ws`);
    
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "transcript") {
        setTranscripts(prev => [data, ...prev].slice(0, 100));
      }
    };

    return () => ws.current?.close();
  }, [isJoined]);

  const joinSession = async () => {
    try {
      const res = await axios.post(`${BACKEND_URL}/api/users/join`, {
        name: userName,
        role: "student",
        session_id: sessionId
      });
      setUserId(res.data.id);
      setIsJoined(true);
    } catch (err) {
      console.error(err);
      alert("Error joining session. Ensure backend is running and session exists.");
    }
  };

  const askQuestion = async () => {
    try {
      await axios.post(`${BACKEND_URL}/api/sessions/${sessionId}/escalation`, {
        student_id: userName,
        tag: "Question",
        query: question
      });
      setQuestion("");
    } catch (err) {
      console.error(err);
      alert("Failed to send question.");
    }
  };

  const sendEscalation = async (tag) => {
    try {
      await axios.post(`${BACKEND_URL}/api/sessions/${sessionId}/escalation`, {
        student_id: userName,
        tag: tag,
        query: `The student marked this as ${tag}`
      });
      alert(`Flagged as: ${tag}`);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="container">
      <div className="header">
        <h1>Student Dashboard</h1>
        {isJoined && <span className="status-badge">● CONNECTED</span>}
      </div>

      {!isJoined ? (
        <div className="card">
          <h3>Join the Class</h3>
          <input className="input" placeholder="Your Name" value={userName} onChange={e => setUserName(e.target.value)} />
          <button className="btn" onClick={joinSession}>Join Session</button>
        </div>
      ) : (
        <div style={{display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "2rem"}}>
          <div className="card">
            <h3><Mic size={18} /> Real-time Transcription</h3>
            <div className="transcript-area">
              {transcripts.map((t, i) => (
                <div key={i} className="transcript-item" style={{opacity: t.is_final ? 1 : 0.6}}>
                  <span className="speaker">{t.speaker}:</span> {t.text}
                </div>
              ))}
            </div>
          </div>

          <div style={{display: "flex", flexDirection: "column", gap: "1rem"}}>
            <div className="card" style={{border: "2px solid #fee2e2"}}>
              <h3 style={{color: "#dc2626"}}><AlertCircle size={18} /> I'm Confused</h3>
              <p style={{fontSize: "0.85rem", marginBottom: "1rem"}}>Click a tag below to anonymously notify the professor that the current topic is unclear.</p>
              <div style={{display: "flex", flexWrap: "wrap", gap: "0.5rem"}}>
                {["Too Fast", "Unclear Concept", "Need Example", "Explain Again"].map(tag => (
                  <button key={tag} className="btn btn-secondary" onClick={() => sendEscalation(tag)} style={{fontSize: "0.8rem"}}>
                    {tag}
                  </button>
                ))}
              </div>
            </div>

            <div className="card">
              <h3><HelpCircle size={18} /> Ask a Question</h3>
              <textarea 
                className="input" 
                style={{height: "80px"}} 
                placeholder="Type your question..." 
                value={question} 
                onChange={e => setQuestion(e.target.value)}
              />
              <button className="btn" onClick={askQuestion}>
                <Send size={18} style={{marginRight: 8}} /> Send
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
