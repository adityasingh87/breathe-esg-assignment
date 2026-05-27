import React, { useState, useEffect } from 'react';
import { Upload, FileText, AlertCircle, CheckCircle2, Clock } from 'lucide-react';
import { uploadFile, getJobs, getJobErrors } from '../services/api';

const IngestionPanel = () => {
  const [sourceType, setSourceType] = useState('sap');
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [jobErrors, setJobErrors] = useState([]);

  const fetchJobs = async () => {
    try {
      const data = await getJobs();
      setJobs(data.results || []);
    } catch (error) {
      console.error('Failed to fetch jobs', error);
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;
    
    setUploading(true);
    try {
      await uploadFile(sourceType, file);
      setFile(null);
      document.getElementById('file-upload').value = '';
      fetchJobs();
    } catch (error) {
      console.error('Upload failed', error);
      alert('Upload failed. Check console.');
    } finally {
      setUploading(false);
    }
  };

  const viewErrors = async (jobId) => {
    try {
      const errors = await getJobErrors(jobId);
      setJobErrors(errors.results || errors);
      setSelectedJob(jobId);
    } catch (error) {
      console.error('Failed to fetch errors', error);
    }
  };

  const StatusIcon = ({ status }) => {
    switch(status) {
      case 'done': return <CheckCircle2 size={18} className="status-icon done" />;
      case 'failed': return <AlertCircle size={18} className="status-icon failed" />;
      case 'processing': return <Clock size={18} className="status-icon processing" />;
      default: return <Clock size={18} className="status-icon" style={{color: 'var(--text-muted)'}} />;
    }
  };

  return (
    <div className="ingestion-layout animate-fade-in">
      {/* Upload Section */}
      <div>
        <div className="card">
          <div className="card-header">
            <Upload size={20} className="text-blue" />
            New Ingestion
          </div>
          <form onSubmit={handleUpload}>
            <div className="form-group">
              <label>Data Source</label>
              <select value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
                <option value="sap">SAP (Fuel & Procurement)</option>
                <option value="utility">Utility (Electricity)</option>
                <option value="travel">Corporate Travel (Air, Hotel)</option>
              </select>
            </div>
            <div className="form-group">
              <label>CSV File</label>
              <input id="file-upload" type="file" accept=".csv" onChange={handleFileChange} />
            </div>
            <button type="submit" disabled={!file || uploading} className="btn btn-primary" style={{marginTop: '1rem'}}>
              {uploading ? 'Uploading...' : 'Upload & Process'}
            </button>
          </form>
        </div>
      </div>

      {/* Jobs List Section */}
      <div>
        <div className="card">
          <div className="card-header">
            <FileText size={20} className="text-green" />
            Recent Jobs
          </div>
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>File Name</th>
                  <th>Source</th>
                  <th>Rows (Valid / Error)</th>
                  <th>Time</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map(job => (
                  <tr key={job.id}>
                    <td>
                      <div className="status-wrapper">
                        <StatusIcon status={job.status} />
                        <span className="capitalize">{job.status}</span>
                      </div>
                    </td>
                    <td className="text-highlight">{job.file_name}</td>
                    <td className="uppercase">{job.source_type}</td>
                    <td>
                      {job.parsed_rows || 0} / <span className={job.error_rows > 0 ? "text-error" : ""}>{job.error_rows || 0}</span>
                    </td>
                    <td style={{fontSize: '0.75rem'}}>{new Date(job.ingested_at).toLocaleString()}</td>
                    <td>
                      {job.error_rows > 0 && (
                        <button onClick={() => viewErrors(job.id)} className="btn btn-secondary" style={{padding: '4px 8px', fontSize: '0.75rem', width: 'auto'}}>
                          Errors
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {jobs.length === 0 && (
                  <tr>
                    <td colSpan="6" className="empty-state">No ingestion jobs yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Errors Panel */}
        {selectedJob && (
          <div className="card errors-panel fade-up">
            <div className="errors-panel-header">
              <h3>
                <AlertCircle size={20} />
                Errors for Job
              </h3>
              <button onClick={() => setSelectedJob(null)} className="close-btn">✕</button>
            </div>
            <div style={{maxHeight: '250px', overflowY: 'auto'}}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Code</th>
                    <th>Message</th>
                  </tr>
                </thead>
                <tbody>
                  {jobErrors.map((err, i) => (
                    <tr key={i}>
                      <td>{err.row_number}</td>
                      <td className="font-mono">{err.error_code}</td>
                      <td style={{color: 'var(--red)'}}>{err.error_message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default IngestionPanel;
