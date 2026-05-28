import React, { useState } from 'react';
import { login } from '../services/api';

const Login = ({ onLogin }) => {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await login(username, password);
      onLogin();
    } catch (err) {
      console.error(err);
      if (err.message === 'Network Error') {
        setError(`Cannot connect to backend: ${err.message}`);
      } else if (err.response && err.response.status === 401) {
        setError('Incorrect username or password');
      } else {
        setError(`Error: ${err.message}`);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen animate-fade-in">
      <div className="card login-box">
        <h2>Breathe ESG</h2>
        {error && <div className="error-msg">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="login-form-group">
            <label>Username</label>
            <input 
              type="text" 
              value={username} 
              onChange={e => setUsername(e.target.value)}
              required
            />
          </div>
          <div className="login-form-group">
            <label>Password</label>
            <input 
              type="password" 
              value={password} 
              onChange={e => setPassword(e.target.value)}
              required
            />
          </div>
          <button type="submit" disabled={loading} className="btn btn-primary" style={{marginTop: '0.5rem'}}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Login;
