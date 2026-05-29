import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Upload, Database, LogOut } from 'lucide-react';
import IngestionPanel from './components/IngestionPanel';
import AnalystGrid from './components/AnalystGrid';
import AnalyticsDashboard from './components/AnalyticsDashboard';
import Login from './components/Login';
import { logout } from './services/api';

const NavLink = ({ to, icon: Icon, children }) => {
  const location = useLocation();
  const isActive = location.pathname === to;
  
  return (
    <Link to={to} className={`nav-link ${isActive ? 'active' : ''}`}>
      <Icon size={18} />
      {children}
    </Link>
  );
};

const App = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      setIsAuthenticated(true);
    }
  }, []);

  const handleLogout = () => {
    logout();
    setIsAuthenticated(false);
  };

  if (!isAuthenticated) {
    return <Login onLogin={() => setIsAuthenticated(true)} />;
  }

  return (
    <Router>
      {/* Navigation Bar */}
      <nav className="top-nav animate-fade-in">
        <div style={{display: 'flex', gap: '2rem', alignItems: 'center'}}>
          <h1 className="nav-brand">Breathe ESG</h1>
          <div className="nav-links">
            <NavLink to="/" icon={LayoutDashboard}>Dashboard</NavLink>
            <NavLink to="/ingest" icon={Upload}>Ingestion</NavLink>
            <NavLink to="/grid" icon={Database}>Analyst Grid</NavLink>
          </div>
        </div>
        
        <div className="nav-user">
          <div className="nav-tenant">
            Tenant: <span>Acme Corp</span>
          </div>
          <button onClick={handleLogout} className="nav-logout" title="Logout" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500, fontSize: '0.875rem' }}>
            <LogOut size={18} /> Logout
          </button>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="main-content">
        <Routes>
          <Route path="/" element={<AnalyticsDashboard />} />
          <Route path="/ingest" element={<IngestionPanel />} />
          <Route path="/grid" element={<AnalystGrid />} />
        </Routes>
      </main>
    </Router>
  );
};

export default App;
