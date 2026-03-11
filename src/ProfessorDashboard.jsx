import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { Play, MessageCircle, BookOpen, AlertCircle, Sparkles } from "lucide-react";
import TranscriptWindow from "./TranscriptWindow";

const BACKEND_URL = "https://0416-131-239-113-82.ngrok-free.app";

export default function ProfessorDashboard() {
  const [zoomUrl, setZoomUrl] = useState("");
  const [topic, setTopic] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [incomingTranscript, setIncomingTranscript] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [isLive, setIsLive] = useState(false);
  const ws = useRef(null);

  useEffect(() => {
    if (!isLive) return;
    
    ws.current = new WebSocket(`${BACKEND_URL.replace("https", "wss")}/api/recall/ws`);
    
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "transcript") {
        setIncomingTranscript(data);
      } else if (data.type === "new_question") {
        setQuestions(prev => [data.question, ...prev]);
      } else if (data.type === "escalation_added") {
        setQuestions(prev => [{
            id: data.data.id,
            student_name: data.data.student_id,
            text: data.data.tag + ": " + data.data.query,
            is_escalation: true
        }, ...prev]);
      } else if (data.type === "ai_answer") {
        setQuestions(prev => prev.map(q => 
          q.id === data.question_id ? { ...q, ai_answer: data.answer } : q
        ));
      }
    };

    return () => ws.current?.close();
  }, [isLive]);

  const startSession = async () => {
    try {
      await axios.put(`${BACKEND_URL}/api/topic`, { topic });
      const res = await axios.post(`${BACKEND_URL}/api/recall/join?meeting_url=${encodeURIComponent(zoomUrl)}&session_id=session-001`);
      setSessionId(res.data.session_id);
      setIsLive(true);
    } catch (err) {
      alert("Error starting session.");
    }
  };

  const handleAIAnswer = async (questionId) => {
    try {
      await axios.post(`${BACKEND_URL}/api/ai/answer`, {
        session_id: "session-001",
        question_id: questionId
      });
    } catch (err) {
      alert("AI failed to generate answer.");
    }
  };

  return (
    <div className="container">
      <div className="header">
        <h1>Professor Dashboard</h1>
        {isLive && <span className="status-badge">● LIVE: {topic}</span>}
      </div>

      {!isLive ? (
        <div className="card" style={{maxWidth: "600px", margin: "0 auto"}}>
          <h3>Start New Session</h3>
          <label>Lecture Topic</label>
          <input className="input" placeholder="e.g. Quantum Computing" value={topic} onChange={e => setTopic(e.target.value)} />
          <label>Zoom Meeting URL</label>
          <input className="input" placeholder="Paste link here" value={zoomUrl} onChange={e => setZoomUrl(e.target.value)} />
          <button className="btn" style={{width: "100%"}} onClick={startSession}>
            <Play size={18} /> Launch Bot & Start Class
          </button>
        </div>
      ) : (
        <div style={{display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "2rem"}}>
          <div>
            <TranscriptWindow incomingTranscript={incomingTranscript} sessionId="session-001" />
          </div>

          <div className="card">
            <h3><MessageCircle size={18} /> Interaction Feed</h3>
            <div className="question-list">
              {questions.length === 0 ? <p style={{color: "#94a3b8", padding: "1rem"}}>Waiting for interactions...</p> : 
                questions.map((q, i) => (
                  <div key={i} className="card" style={{borderLeft: q.is_escalation ? "4px solid #ef4444" : "4px solid #3b82f6", background: "#fff", marginBottom: "1rem", padding: "1rem"}}>
                    <div style={{display: "flex", justifyContent: "space-between"}}>
                      <div>
                        <strong>{q.student_name}</strong>
                        <p>{q.text}</p>
                      </div>
                      {!q.ai_answer && (
                        <button className="btn" style={{background: "#7c3aed", fontSize: "0.75rem", padding: "4px 8px"}} onClick={() => handleAIAnswer(q.id)}>
                          <Sparkles size={12} /> AI
                        </button>
                      )}
                    </div>
                    {q.ai_answer && (
                      <div style={{marginTop: "0.5rem", padding: "0.5rem", background: "#f5f3ff", fontSize: "0.9rem", borderRadius: "4px"}}>
                        <strong>AI:</strong> {q.ai_answer}
                      </div>
                    )}
                  </div>
                ))
              }
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
