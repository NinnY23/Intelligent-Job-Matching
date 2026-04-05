// src/App.jsx
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import JobMatch from './JobMatch';
import CreateJobPost from './CreateJobPost';
import Profile from './Profile';
import ResumeExtractionDemo from './ResumeExtractionDemo';
import JobDescriptionExtractionDemo from './JobDescriptionExtractionDemo';
import SkillAdmin from './SkillAdmin';
import CompatibilityCompare from './CompatibilityCompare';
import Login from './Login';
import SignUp from './SignUp';
import ForgotPassword from './ForgotPassword';
import { getProfile, tryDevBootstrapLogin } from './api';
import './App.css';

function Header({ user, currentPage, onLogout, navigate }) {
  return (
    <header>
      <h1>Intelligent Job Matching</h1>
      <div className="nav-links">
        <button 
          className={`nav-link ${currentPage === 'jobs' ? 'active' : ''}`}
          onClick={() => navigate('/jobs')}
        >
          Browse Jobs
        </button>
        <button 
          className={`nav-link ${currentPage === 'create-job' ? 'active' : ''}`}
          onClick={() => navigate('/create-job')}
        >
          Post a Job
        </button>
        <button 
          className={`nav-link ${currentPage === 'profile' ? 'active' : ''}`}
          onClick={() => navigate('/profile')}
        >
          Profile
        </button>
        <button
          className={`nav-link ${currentPage === 'resume-demo' ? 'active' : ''}`}
          onClick={() => navigate('/resume-demo')}
        >
          Test Demo
        </button>
        <button
          className={`nav-link ${currentPage === 'job-pdf-demo' ? 'active' : ''}`}
          onClick={() => navigate('/job-pdf-demo')}
        >
          Job PDF Demo
        </button>
        <button
          className={`nav-link ${currentPage === 'skills-admin' ? 'active' : ''}`}
          onClick={() => navigate('/skills-admin')}
        >
          Skills / jobs
        </button>
        <button
          className={`nav-link ${currentPage === 'compare-extractions' ? 'active' : ''}`}
          onClick={() => navigate('/compare-extractions')}
        >
          Compare extractions
        </button>
      </div>
      <div className="user-info">
        <span>Welcome, {user.name || user.email}</span>
        <button onClick={onLogout} className="logout-btn">Logout</button>
      </div>
    </header>
  );
}

function AppContent() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      const token = localStorage.getItem('token');
      const savedUser = localStorage.getItem('user');
      if (!token || !savedUser) {
        if (!cancelled) setLoading(false);
        return;
      }
      let parsed;
      try {
        parsed = JSON.parse(savedUser);
      } catch {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        if (!cancelled) setLoading(false);
        return;
      }
      try {
        const profile = await getProfile();
        if (cancelled) return;
        const u = profile.user || parsed;
        setUser(u);
        localStorage.setItem('user', JSON.stringify(u));
      } catch {
        const recovered = await tryDevBootstrapLogin();
        if (cancelled) return;
        if (recovered?.user) {
          setUser(recovered.user);
        } else {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          setUser(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleLoginSuccess = (userData) => {
    setUser(userData);
    navigate('/jobs');
  };

  const handleSignUpSuccess = (userData) => {
    setUser(userData);
    navigate('/jobs');
  };

  const handleUpdateProfile = (updatedUser) => {
    setUser(updatedUser);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
    navigate('/login');
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  // If not logged in, show auth routes
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<Login onLoginSuccess={handleLoginSuccess} onSwitchToSignUp={() => navigate('/signup')} onSwitchToForgotPassword={() => navigate('/forgot-password')} />} />
        <Route path="/signup" element={<SignUp onSignUpSuccess={handleSignUpSuccess} onSwitchToLogin={() => navigate('/login')} />} />
        <Route path="/forgot-password" element={<ForgotPassword onSwitchToLogin={() => navigate('/login')} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  // If logged in, show app routes
  return (
    <>
      <Routes>
        <Route path="/create-job" element={
          <>
            <Header user={user} currentPage="create-job" onLogout={handleLogout} navigate={navigate} />
            <CreateJobPost onPostCreated={() => navigate('/jobs')} onBack={() => navigate('/jobs')} />
          </>
        } />
        <Route path="/jobs" element={
          <>
            <Header user={user} currentPage="jobs" onLogout={handleLogout} navigate={navigate} />
            <JobMatch />
          </>
        } />
        <Route path="/profile" element={
          <>
            <Header user={user} currentPage="profile" onLogout={handleLogout} navigate={navigate} />
            <Profile user={user} onUpdateProfile={handleUpdateProfile} onBack={() => navigate('/jobs')} />
          </>
        } />
        <Route path="/resume-demo" element={
          <>
            <Header user={user} currentPage="resume-demo" onLogout={handleLogout} navigate={navigate} />
            <ResumeExtractionDemo />
          </>
        } />
        <Route path="/job-pdf-demo" element={
          <>
            <Header user={user} currentPage="job-pdf-demo" onLogout={handleLogout} navigate={navigate} />
            <JobDescriptionExtractionDemo />
          </>
        } />
        <Route path="/skills-admin" element={
          <>
            <Header user={user} currentPage="skills-admin" onLogout={handleLogout} navigate={navigate} />
            <SkillAdmin />
          </>
        } />
        <Route path="/compare-extractions" element={
          <>
            <Header user={user} currentPage="compare-extractions" onLogout={handleLogout} navigate={navigate} />
            <CompatibilityCompare />
          </>
        } />
        <Route path="*" element={<Navigate to="/jobs" replace />} />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}