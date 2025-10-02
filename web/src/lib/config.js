export const API_BASE = (typeof window !== 'undefined' && window.__API_BASE__)
|| import.meta.env.VITE_API_BASE
|| 'http://localhost:8080';