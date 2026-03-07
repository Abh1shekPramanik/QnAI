import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { Play, MessageCircle, Mic, BookOpen, AlertCircle } from "lucide-react";

const BACKEND_URL = "https://0416-131-239-113-82.ngrok-free.app";

export default function ProfessorDashboard() {
  const [zoomUrl, setZoomUrl] = useState("");
  const [topic, setTopic] = useState("");
  const [sessionId, setSessionId] = useState(null);
  const [transcripts, setTranscripts] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [isLive, setIsLive] = useState(false);
  const ws = useRef(null);

  useEffect(() => {
    if (!isLive) return;
    
    ws.current = new WebSocket(`${BACKEND_URL.replace("https", "wss")}/api/recall/ws`);
    
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "transcript") {
        setTranscripts(prev => [data, ...prev].slice(0, 100));
      } else if (data.type === "new_question") {
        setQuestions(prev => [data.question, ...prev]);
      } else if (data.type === "escalation_added") {
        setQuestions(prev => [{
            student_name: data.data.student_id,
            text: data.data.tag + ": " + data.data.query,
            is_escalation: true
        }, ...prev]);
      }
    };

    return () => ws.current?.close();
  }, [isLive]);

  const startSession = async () => {
    try {
      // 1. Set the topic first (removed trailing slash)
      await axios.put(`${BACKEND_URL}/api/topic`, { topic });
      // 2. Start the Zoom bot
      const res = await axios.post(`${BACKEND_URL}/api/recall/join?meeting_url=${encodeURIComponent(zoomUrl)}&session_id=session-001`);
      setSessionId(res.data.session_id);
      setIsLive(true);
    } catch (err) {
      console.error(err);
      alert("Error starting session. Check backend & ngrok.");
    }
  };

  const handleAIAnswer = async (questionId) => {
    try {
      const res = await axios.post(`${BACKEND_URL}/api/ai/answer`, {
        session_id: "session-001",
        question_id: questionId
      });
      alert("AI Response generated and saved!");
      // Optionally update local state if needed
    } catch (err) {
      console.error(err);
      alert("AI failed to generate an answer.");
    }
  };

  return (
    <div className="container">
      <div className="header">
        <h1>Professor View</h1>
        {isLive && <span className="status-badge">● LIVE Session {sessionId}</span>}
      </div>

      {!isLive ? (
        <div className="card">
          <h3>Set Up Your Lecture</h3>
          <label>Lecture Topic</label>
          <input className="input" placeholder="e.g. Intro to Binary Trees" value={topic} onChange={e => setTopic(e.target.value)} />
          
          <label>Zoom URL</label>
          <input className="input" placeholder="Paste Zoom link" value={zoomUrl} onChange={e => setZoomUrl(e.target.value)} />
          
          <button className="btn" onClick={startSession}>
            <Play size={18} style={{marginRight: 8}} /> Go Live
          </button>
        </div>
      ) : (
        <div style={{display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "2rem"}}>
          <div className="card">
            <div style={{display: "flex", justifyContent: "space-between", marginBottom: "1rem"}}>
              <h3><Mic size={18} /> Live Transcript</h3>
              <span className="topic-display"><BookOpen size={16}/> {topic}</span>
            </div>
            <div className="transcript-area">
              {transcripts.map((t, i) => (
                <div key={i} className="transcript-item" style={{opacity: t.is_final ? 1 : 0.6}}>
                  <span className="speaker">{t.speaker}:</span> {t.text}
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h3><MessageCircle size={18} /> Interaction Feed</h3>
            <div className="question-list">
              {questions.length === 0 ? <p>Waiting for student interaction...</p> : 
                questions.map((q, i) => (
                  <div key={i} className={`question-item ${q.is_escalation ? 'escalation' : ''}`}>
                    {q.is_escalation && <span className="escalation-badge"><AlertCircle size={12}/> STUDENT CONFUSED</span>}
                    <div><strong>{q.student_name}:</strong> {q.text}</div>
                    {q.id && (
                      <button 
                        className="btn btn-secondary" 
                        style={{marginTop: 8, fontSize: "0.75rem", padding: "4px 8px"}}
                        onClick={() => handleAIAnswer(q.id)}
                      >
                        Ask AI to Answer
                      </button>
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
