import React, { useState, useEffect } from 'react';
import { PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts';
import { getSummary, getReviewQueue } from '../services/api';
import { AlertCircle, CheckCircle2, Clock, Lock } from 'lucide-react';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'];

const AnalyticsDashboard = () => {
  const [summary, setSummary] = useState(null);
  const [queue, setQueue] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [sumData, queueData] = await Promise.all([
          getSummary(),
          getReviewQueue()
        ]);
        setSummary(sumData);
        setQueue(queueData);
      } catch (error) {
        console.error("Failed to fetch analytics", error);
      }
    };
    fetchData();
  }, []);

  if (!summary || !queue) return <div className="empty-state">Loading analytics...</div>;

  const scopeData = Object.keys(summary.by_scope).map((key, index) => ({
    name: key.replace('_', ' ').toUpperCase(),
    value: parseFloat(summary.by_scope[key]) || 0,
    color: COLORS[index % COLORS.length]
  })).filter(item => item.value > 0);

  const sourceData = Object.keys(summary.by_source).map((key, index) => ({
    name: key.toUpperCase(),
    value: parseFloat(summary.by_source[key]) || 0,
    color: COLORS[(index + 2) % COLORS.length]
  })).filter(item => item.value > 0);

  const totalEmissions = scopeData.reduce((acc, curr) => acc + curr.value, 0);

  const renderReviewCard = (sourceName, data) => (
    <div key={sourceName} className="card">
      <div className="card-header-small">{sourceName} Queue</div>
      <div className="queue-stats">
        <div className="queue-stat-item">
          <Clock size={16} className="text-amber" style={{marginBottom: '4px'}} />
          <span className="queue-stat-val">{data.pending || 0}</span>
          <span className="queue-stat-label">Pending</span>
        </div>
        <div className="queue-stat-item">
          <CheckCircle2 size={16} className="text-green" style={{marginBottom: '4px'}} />
          <span className="queue-stat-val">{data.approved || 0}</span>
          <span className="queue-stat-label">Approved</span>
        </div>
        <div className="queue-stat-item">
          <AlertCircle size={16} className="text-red" style={{marginBottom: '4px'}} />
          <span className="queue-stat-val">{data.flagged || 0}</span>
          <span className="queue-stat-label">Flagged</span>
        </div>
        <div className="queue-stat-item">
          <Lock size={16} className="text-blue" style={{marginBottom: '4px'}} />
          <span className="queue-stat-val">{data.locked || 0}</span>
          <span className="queue-stat-label">Locked</span>
        </div>
      </div>
    </div>
  );

  return (
    <div className="animate-fade-in">
      
      {/* Top Cards */}
      <div className="dashboard-top">
        <div className="card total-emissions-card">
          <div className="card-header-small" style={{borderBottom: 'none'}}>Total Emissions</div>
          <div className="total-value">
            {totalEmissions.toLocaleString(undefined, {maximumFractionDigits: 0})}
          </div>
          <div className="total-unit">kg CO₂e</div>
        </div>
        
        <div className="queue-grid">
          {Object.keys(queue).map(source => renderReviewCard(source, queue[source]))}
        </div>
      </div>

      {/* Charts */}
      <div className="charts-grid">
        
        <div className="card">
          <div className="card-header-small">Emissions by Scope</div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={scopeData} cx="50%" cy="50%" innerRadius={60} outerRadius={90}
                  paddingAngle={5} dataKey="value" stroke="none"
                >
                  {scopeData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <RechartsTooltip 
                  formatter={(value) => [`${value.toFixed(2)} kg CO₂e`, 'Emissions']}
                  contentStyle={{ backgroundColor: '#111d30', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '10px', color: '#fff' }}
                  itemStyle={{ color: '#8b9bbf' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-legend">
            {scopeData.map(entry => (
              <div key={entry.name} className="chart-legend-item">
                <div className="legend-color" style={{backgroundColor: entry.color}}></div>
                {entry.name}
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header-small">Emissions by Source Type</div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sourceData} layout="vertical" margin={{ top: 0, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" stroke="#8b9bbf" fontSize={12} tickFormatter={(val) => `${val/1000}k`} />
                <YAxis dataKey="name" type="category" stroke="#8b9bbf" fontSize={10} width={70} />
                <RechartsTooltip 
                  cursor={{fill: 'rgba(255,255,255,0.02)'}}
                  formatter={(value) => [`${value.toFixed(2)} kg CO₂e`, 'Emissions']}
                  contentStyle={{ backgroundColor: '#111d30', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '10px', color: '#fff' }}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {sourceData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

      </div>

    </div>
  );
};

export default AnalyticsDashboard;
