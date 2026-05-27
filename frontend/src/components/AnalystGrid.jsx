import React, { useState, useEffect } from 'react';
import { Edit2, CheckCircle2, Flag, Lock, Activity, RefreshCw } from 'lucide-react';
import api, { getRecords, updateRecord, approveRecord, flagRecord } from '../services/api';

const AnalystGrid = () => {
  const [records, setRecords] = useState([]);
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ review_status: 'pending' });
  const [auditLogs, setAuditLogs] = useState([]);
  const [actionMsg, setActionMsg] = useState('');

  // Sidebar edit state
  const [editForm, setEditForm] = useState({
    raw_quantity: '',
    raw_unit: '',
    description: ''
  });

  const fetchRecords = async () => {
    setLoading(true);
    try {
      const data = await getRecords(filters);
      setRecords(data.results || []);
    } catch (error) {
      console.error('Fetch records failed', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecords();
  }, [filters]);

  const handleRowClick = async (record) => {
    setSelectedRecord(record);
    setActionMsg('');
    setEditForm({
      raw_quantity: record.raw_quantity,
      raw_unit: record.raw_unit,
      description: record.description || ''
    });
    // Fetch audit logs
    try {
      const { data } = await api.get(`/v1/records/${record.id}/audit/`);
      setAuditLogs(data);
    } catch (e) {
      console.error(e);
      setAuditLogs([]);
    }
  };

  const handleSaveEdit = async () => {
    try {
      await updateRecord(selectedRecord.id, editForm);
      setActionMsg('✓ Saved successfully');
      await fetchRecords();
      setSelectedRecord(null);
    } catch (e) {
      console.error(e);
      setActionMsg('✗ Save failed');
    }
  };

  const handleApprove = async () => {
    try {
      await approveRecord(selectedRecord.id);
      setActionMsg('✓ Record approved');
      await fetchRecords();
      setSelectedRecord(null);
    } catch (e) {
      console.error('Approve error:', e.response?.data || e.message);
      setActionMsg('✗ Approve failed: ' + (e.response?.data?.error || e.message));
    }
  };

  const handleFlag = async () => {
    try {
      await flagRecord(selectedRecord.id, 'Flagged for review');
      setActionMsg('✓ Record flagged');
      await fetchRecords();
      setSelectedRecord(null);
    } catch (e) {
      console.error('Flag error:', e.response?.data || e.message);
      setActionMsg('✗ Flag failed: ' + (e.response?.data?.error || e.message));
    }
  };

  const handleLock = async () => {
    try {
      await api.post(`/v1/records/${selectedRecord.id}/lock/`);
      setActionMsg('✓ Record locked');
      await fetchRecords();
      setSelectedRecord(null);
    } catch (e) {
      console.error('Lock error:', e.response?.data || e.message);
      setActionMsg('✗ Lock failed: ' + (e.response?.data?.error || e.message));
    }
  };

  return (
    <div className="analyst-layout animate-fade-in">
      
      {/* Main Grid Area */}
      <div className={`card analyst-main ${selectedRecord ? 'with-sidebar' : ''}`} style={{padding: 0}}>
        
        {/* Toolbar */}
        <div className="toolbar">
          <div className="toolbar-left">
            <h2><Activity size={20} className="text-blue" /> Analyst Grid</h2>
            <select 
              className="filter-select"
              value={filters.review_status}
              onChange={e => setFilters({...filters, review_status: e.target.value})}
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="flagged">Flagged</option>
              <option value="locked">Locked</option>
            </select>
          </div>
          <button onClick={fetchRecords} className="icon-btn">
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {/* Table */}
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Scope</th>
                <th>Category</th>
                <th>Date</th>
                <th>Qty</th>
                <th>Emissions (kg CO₂e)</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {records.map(r => (
                <tr 
                  key={r.id} 
                  onClick={() => handleRowClick(r)}
                  className={selectedRecord?.id === r.id ? 'active' : ''}
                >
                  <td className="capitalize">{r.scope ? r.scope.replace('_', ' ') : '-'}</td>
                  <td className="text-highlight">{r.category}</td>
                  <td>{r.activity_date}</td>
                  <td>{Number(r.raw_quantity).toFixed(2)} {r.raw_unit}</td>
                  <td className="text-blue">
                    {r.normalized_quantity_kg ? Number(r.normalized_quantity_kg).toFixed(2) : '-'}
                  </td>
                  <td>
                    <span className={`badge badge-${r.review_status}`}>
                      {r.review_status}
                    </span>
                  </td>
                </tr>
              ))}
              {records.length === 0 && !loading && (
                <tr>
                  <td colSpan="6" className="empty-state">No records found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Sidebar / Detail Panel */}
      {selectedRecord && (
        <div className="card analyst-sidebar fade-up" style={{padding: 0}}>
          
          <div className="sidebar-header">
            <h3>Record Details</h3>
            <button onClick={() => setSelectedRecord(null)} className="icon-btn" style={{fontSize: '1.25rem'}}>✕</button>
          </div>
          
          <div className="sidebar-content">
            
            {/* Action feedback message */}
            {actionMsg && (
              <div style={{
                padding: '8px 12px', borderRadius: '8px', fontSize: '0.8rem', marginBottom: '1rem',
                background: actionMsg.startsWith('✓') ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
                color: actionMsg.startsWith('✓') ? 'var(--green-light)' : 'var(--red)',
                border: `1px solid ${actionMsg.startsWith('✓') ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`
              }}>
                {actionMsg}
              </div>
            )}

            {/* Quick Actions */}
            {selectedRecord.review_status !== 'locked' && (
              <div className="quick-actions">
                <button onClick={handleApprove} className="btn btn-success">
                  <CheckCircle2 size={14}/> Approve
                </button>
                <button onClick={handleFlag} className="btn btn-danger">
                  <Flag size={14}/> Flag
                </button>
                {selectedRecord.review_status === 'approved' && (
                  <button onClick={handleLock} className="btn btn-secondary">
                    <Lock size={14}/> Lock
                  </button>
                )}
              </div>
            )}
            
            {/* Edit Form */}
            <div>
              <h4 className="section-title">Edit Data</h4>
              <div className="form-group">
                <label>Raw Quantity</label>
                <input 
                  type="number" step="0.01" 
                  value={editForm.raw_quantity} 
                  onChange={e => setEditForm({...editForm, raw_quantity: e.target.value})}
                  disabled={selectedRecord.review_status === 'locked'}
                />
              </div>
              <div className="form-group">
                <label>Unit</label>
                <input 
                  type="text" 
                  value={editForm.raw_unit} 
                  onChange={e => setEditForm({...editForm, raw_unit: e.target.value})}
                  disabled={selectedRecord.review_status === 'locked'}
                />
              </div>
              <div className="form-group">
                <label>Description</label>
                <textarea 
                  value={editForm.description || ''} 
                  onChange={e => setEditForm({...editForm, description: e.target.value})}
                  disabled={selectedRecord.review_status === 'locked'}
                  rows="2"
                />
              </div>
              {selectedRecord.review_status !== 'locked' && (
                <button onClick={handleSaveEdit} className="btn btn-primary">
                  <Edit2 size={16}/> Save Changes
                </button>
              )}
            </div>
            
            {/* Raw Payload Preview */}
            <div>
              <h4 className="section-title">Source Payload</h4>
              <pre className="payload-preview">
                {JSON.stringify(selectedRecord.raw_payload, null, 2)}
              </pre>
            </div>

            {/* Audit Logs */}
            <div>
              <h4 className="section-title">Audit Trail</h4>
              {auditLogs.length === 0 ? (
                <p className="empty-state" style={{padding: '1rem'}}>No logs.</p>
              ) : (
                <div className="audit-timeline">
                  {auditLogs.map(log => (
                    <div key={log.id} className="audit-item">
                      <div className="audit-item-header">
                        <span className="audit-action">{log.action}</span>
                        <span className="audit-time">{new Date(log.changed_at).toLocaleString()}</span>
                      </div>
                      <div className="audit-user">By: {log.changed_by}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

          </div>
        </div>
      )}
    </div>
  );
};

export default AnalystGrid;
