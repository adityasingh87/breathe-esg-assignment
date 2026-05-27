import axios from 'axios';

const API_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token');
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

export const login = async (username, password) => {
  const response = await axios.post('http://localhost:8000/api/auth/token/', { username, password });
  localStorage.setItem('token', response.data.access);
  return response.data;
};

export const logout = () => {
  localStorage.removeItem('token');
};

export const uploadFile = async (sourceType, file) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post(`/v1/ingest/${sourceType}/`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  return response.data;
};

export const getJobs = async () => {
  const response = await api.get('/v1/jobs/');
  return response.data;
};

export const getJobErrors = async (jobId) => {
  const response = await api.get(`/v1/jobs/${jobId}/errors/`);
  return response.data;
};

export const getRecords = async (params) => {
  const response = await api.get('/v1/records/', { params });
  return response.data;
};

export const updateRecord = async (id, data) => {
  const response = await api.patch(`/v1/records/${id}/`, data);
  return response.data;
};

export const approveRecord = async (id) => {
  const response = await api.post(`/v1/records/${id}/approve/`);
  return response.data;
};

export const flagRecord = async (id, reason) => {
  const response = await api.post(`/v1/records/${id}/flag/`, { reason });
  return response.data;
};

export const getSummary = async () => {
  const response = await api.get('/v1/summary/');
  return response.data;
};

export const getReviewQueue = async () => {
  const response = await api.get('/v1/summary/review-queue/');
  return response.data;
};

export default api;
