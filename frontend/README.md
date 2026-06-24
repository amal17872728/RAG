Wikipedia RAG Frontend

Quick start:

1. cd frontend
2. npm install
3. VITE_API_BASE=http://localhost:8000 npm run dev

The Docker image builds the app with `VITE_API_BASE=http://localhost:${BACKEND_PORT}` and serves the production build with `vite preview`.
