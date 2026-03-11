import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { Send, MessageCircle, AlertCircle, HelpCircle, Sparkles } from "lucide-react";
import TranscriptWindow from "./TranscriptWindow";

const BACKEND_URL = "https://0416-131-239-113-82.ngrok-free.app";

export default function StudentDashboard() {
  const [sessionId, setSessionId] = useState("session-001");
  const [userName, setUserName] = useState("");
  const [userId, setUserId] = useState(null);
  const [question, setQuestion] = useState("");
  const [incomingTranscript, setIncomingTranscript] = useState(null);
  const [aiAnswers, setAiAnswers] = useState([]);
  const [isJoined, setIsJoined] = useState(false);
  const ws = useRef(null);

  useEffect(() => {
    if (!isJoined) return;
    
    ws.current = new WebSocket(`${BACKEND_URL.replace("https", "wss")}/api/recall/ws`);
    
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "transcript") {
        setIncomingTranscript(data);
      } else if (data.type === "ai_answer") {
        setAiAnswers(prev => [data, ...prev]);
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
      alert("Error joining session.");
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
      alert("Sent!");
    } catch (err) {
      alert("Failed to send.");
    }
  };

  const sendEscalation = async (tag) => {
    try {
      await axios.post(`${BACKEND_URL}/api/sessions/${sessionId}/escalation`, {
        student_id: userName,
        tag: tag,
        query: "Student flagged"
      });
      alert(`Professor notified: ${tag}`);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="container">
      <div className="header">
        <h1>Student Portal</h1>
        {isJoined && <span className="status-badge">● CONNECTED</span>}
      </div>

      {!isJoined ? (
        <div className="card" style={{maxWidth: "500px", margin: "0 auto"}}>
          <h3>Join Lecture</h3>
          <input className="input" placeholder="Your Full Name" value={userName} onChange={e => setUserName(e.target.value)} />
          <button className="btn" style={{width: "100%"}} onClick={joinSession}>Enter</button>
        </div>
      ) : (
        <div style={{display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "2rem"}}>
          <div>
            <TranscriptWindow incomingTranscript={incomingTranscript} sessionId={sessionId} />
            <div className="card" style={{marginTop: "1rem", border: "1px solid #7c3aed"}}>
              <h3 style={{color: "#7c3aed"}}><Sparkles size={18} /> AI Answers</h3>
              <div style={{maxHeight: "200px", overflowY: "auto"}}>
                {aiAnswers.length === 0 ? <p style={{fontSize: "0.9rem", color: "#94a3b8"}}>Your answers will appear here.</p> : 
                  aiAnswers.map((ans, i) => (
                    <div key={i} style={{padding: "0.75rem", background: "#f5f3ff", borderRadius: "6px", marginBottom: "0.5rem", fontSize: "0.9rem"}}>
                      {ans.answer}
                    </div>
                  ))
                }
              </div>
            </div>
          </div>

          <div style={{display: "flex", flexDirection: "column", gap: "1rem"}}>
            <div className="card" style={{background: "#fef2f2"}}>
              <h3 style={{color: "#991b1b"}}><AlertCircle size={18} /> Confusion</h3>
              <div style={{display: "flex", flexWrap: "wrap", gap: "0.5rem"}}>
                {["Too Fast", "Need Example", "Explain Again"].map(tag => (
                  <button key={tag} className="btn btn-secondary" style={{fontSize: "0.75rem", color: "#991b1b", background: "#fff"}} onClick={() => sendEscalation(tag)}>
                    {tag}
                  </button>
                ))}
              </div>
            </div>

            <div className="card">
              <h3><MessageCircle size={18} /> Ask Question</h3>
              <textarea className="input" style={{height: "80px"}} placeholder="Ask anything..." value={question} onChange={e => setQuestion(e.target.value)} />
              <button className="btn" onClick={askQuestion}><Send size={16} /> Send</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
