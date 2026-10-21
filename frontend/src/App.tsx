import { useState, useEffect } from "react";
import { api, HealthResponse } from "./api/client";
import "./App.css";

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await api.health();
        setHealth(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        <span>Loading...</span>
      </div>
    );
  }

  return (
    <div className="container">
      <header style={{ marginBottom: "2rem", paddingBottom: "1rem", borderBottom: "1px solid #e5e7eb" }}>
        <h1 style={{ fontSize: "1.875rem", fontWeight: 700, color: "#1a1a2e" }}>
          Prism Studio
        </h1>
        <p style={{ color: "#6b7280", marginTop: "0.5rem" }}>
          Turn codebases into queryable knowledge graphs
        </p>
      </header>

      {error && (
        <div className="error-message">
          <strong>Backend unavailable:</strong> {error}
        </div>
      )}

      <div className="card">
        <h2 style={{ marginBottom: "1rem", fontSize: "1.25rem" }}>System Status</h2>
        {health ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", alignItems: "center" }}>
            <div>
              <strong>Application:</strong> {health.app}
            </div>
            <div>
              <strong>Version:</strong> {health.version}
            </div>
            <div>
              <strong>Database:</strong>
              <span
                className={`status-badge ${health.database === "connected" ? "status-healthy" : "status-unhealthy"}`}
              >
                {health.database}
              </span>
            </div>
            <div>
              <strong>Overall:</strong>
              <span
                className={`status-badge ${health.status === "healthy" ? "status-healthy" : "status-unhealthy"}`}
              >
                {health.status}
              </span>
            </div>
          </div>
        ) : (
          <div className="loading">
            <div className="spinner" />
            <span>Checking backend...</span>
          </div>
        )}
      </div>

      <div className="card">
        <h2 style={{ marginBottom: "1rem", fontSize: "1.25rem" }}>Quick Actions</h2>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button className="btn btn-primary" disabled={!health || health.status !== "healthy"}>
            Parse Codebase
          </button>
          <button className="btn btn-secondary" disabled={!health || health.status !== "healthy"}>
            View Graph
          </button>
          <button className="btn btn-secondary" disabled={!health || health.status !== "healthy"}>
            Export Graph
          </button>
        </div>
        <p style={{ marginTop: "1rem", color: "#6b7280", fontSize: "0.875rem" }}>
          Graph parsing and visualization coming in next iteration.
        </p>
      </div>

      <footer style={{ marginTop: "2rem", paddingTop: "1rem", borderTop: "1px solid #e5e7eb", color: "#9ca3af", fontSize: "0.875rem" }}>
        <p>Prism Studio — Ryan Vo ryandtvo@gmail.com | AI & Machine Learning</p>
      </footer>
    </div>
  );
}

export default App;