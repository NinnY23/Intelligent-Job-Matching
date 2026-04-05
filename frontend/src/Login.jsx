// src/Login.jsx
import React, { useState } from 'react';
import { loginUser, DEV_BOOTSTRAP_EMAIL } from './api';
import './Login.css';

export default function Login({ onLoginSuccess, onSwitchToSignUp, onSwitchToForgotPassword }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const data = await loginUser(email, password);
      localStorage.setItem('token', data.token);
      localStorage.setItem('user', JSON.stringify(data.user));
      onLoginSuccess(data.user);
    } catch (err) {
      setError(err.message || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-box">
        <h1>Intelligent Job Matching</h1>
        <h2>Login</h2>
        
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email:</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password:</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" disabled={loading} className="login-btn">
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="login-footer">
          <p>Don't have an account? <a href="#signup" onClick={onSwitchToSignUp}>Sign up</a></p>
          <p><a href="#forgot" onClick={onSwitchToForgotPassword}>Forgot password?</a></p>
          {process.env.NODE_ENV === 'development' && (
            <p className="login-dev-hint">
              Dev default account: <code>{DEV_BOOTSTRAP_EMAIL}</code> / <code>dev</code>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
