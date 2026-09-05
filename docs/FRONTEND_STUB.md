# Minimal Front-End Integration Stub (React / Vite)

This guide provides a minimal React component demonstrating how a front-end client communicates with the `control-bim-pf-engine` API.

---

## 1. Quick Example Component (`FeasibilityStudio.jsx`)

```jsx
import React, { useState, useEffect } from 'react';

const API_BASE = 'http://localhost:8000/api/v1';

export default function FeasibilityStudio() {
  const [inputType, setInputType] = useState('interior');
  const [targetStyle, setTargetStyle] = useState('tropical-boutique');
  const [runId, setRunId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  // 1. Submit Generation Case
  const handleGenerate = async () => {
    setLoading(true);
    setJobStatus(null);
    try {
      const res = await fetch(`${API_BASE}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          caseId: `studio-${Date.now()}`,
          inputType,
          targetStyle,
          localImagePath: `tests/fixtures/sample_${inputType}.png`,
          dryRun: false, // set true for offline dev
        }),
      });
      const data = await res.json();
      setRunId(data.runId);
    } catch (err) {
      console.error('Failed to submit:', err);
      setLoading(false);
    }
  };

  // 2. Poll Status
  useEffect(() => {
    if (!runId || (jobStatus && ['done', 'failed'].includes(jobStatus.status))) {
      return;
    }

    const interval = setInterval(async () => {
      const res = await fetch(`${API_BASE}/status/${runId}`);
      const data = await res.json();
      setJobStatus(data);
      if (['done', 'failed'].includes(data.status)) {
        setLoading(false);
        clearInterval(interval);
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [runId, jobStatus]);

  return (
    <div style={{ maxWidth: 800, margin: '40px auto', fontFamily: 'sans-serif' }}>
      <h2>Pre-Feasibility Studio (control-bim-pf-engine)</h2>

      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <select value={inputType} onChange={(e) => setInputType(e.target.value)}>
          <option value="interior">Interior</option>
          <option value="facade">Facade</option>
          <option value="floorplan">Floorplan</option>
        </select>

        <select value={targetStyle} onChange={(e) => setTargetStyle(e.target.value)}>
          <option value="tropical-boutique">Tropical-Boutique Resort</option>
          <option value="luxury-minimal">Modern Luxury Minimalist</option>
          <option value="midrange-modern">Midrange Modern</option>
          <option value="budget-functional">Budget Functional</option>
        </select>

        <button onClick={handleGenerate} disabled={loading} style={{ padding: '8px 16px' }}>
          {loading ? 'Generating...' : 'Generate Visual Concept'}
        </button>
      </div>

      {jobStatus && (
        <div style={{ border: '1px solid #ccc', borderRadius: 8, padding: 16 }}>
          <h4>Status: {jobStatus.status.toUpperCase()} ({Math.round(jobStatus.progress * 100)}%)</h4>
          {jobStatus.latencyMs && <p>Latency: {jobStatus.latencyMs} ms | Silhouette IoU: {jobStatus.iou}</p>}

          {jobStatus.status === 'done' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <h5>Output Render</h5>
                <img
                  src={`http://localhost:8000${Object.values(jobStatus.artifactPaths)[0]}`}
                  alt="Render output"
                  style={{ width: '100%', borderRadius: 6 }}
                />
              </div>
              <div>
                <h5>Artifacts</h5>
                <a href={`http://localhost:8000/api/v1/artifacts/${runId}?download=zip`}>
                  Download Artifacts ZIP
                </a>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```
