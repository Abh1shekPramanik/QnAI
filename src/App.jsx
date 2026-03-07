import React from "react";
import { BrowserRouter as Router, Routes, Route, Link } from "react-router-dom";
import ProfessorDashboard from "./ProfessorDashboard";
import StudentDashboard from "./StudentDashboard";
import "./index.css";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/professor" element={<ProfessorDashboard />} />
        <Route path="/student" element={<StudentDashboard />} />
      </Routes>
    </Router>
  );
}

function Home() {
  return (
    <div className="container" style={{textAlign: "center", marginTop: "10%"}}>
      <h1 style={{fontSize: "3.5rem", color: "#2563eb", marginBottom: "0.5rem"}}>QnAI</h1>
      <p style={{fontSize: "1.2rem", color: "#64748b"}}>Real-time classroom transcription and AI-powered Q&A.</p>
      
      <div style={{display: "flex", justifyContent: "center", gap: "2rem", marginTop: "3rem"}}>
        <Link to="/professor" className="btn" style={{textDecoration: "none"}}>
          I'm the Professor
        </Link>
        <Link to="/student" className="btn btn-secondary" style={{textDecoration: "none"}}>
          I'm a Student
        </Link>
      </div>
    </div>
  );
}

export default App;
