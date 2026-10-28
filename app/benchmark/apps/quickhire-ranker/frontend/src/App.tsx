import React, { useEffect, useState } from "react";

type Candidate = { email: string; score: number; status: string };

export default function App() {
  const [jobId, setJobId] = useState("42");
  const [rows, setRows] = useState<Candidate[]>([]);

  useEffect(() => {
    fetch(`/ranking/${jobId}`).then((r) => r.json()).then(setRows);
  }, [jobId]);

  return (
    <main>
      <h1>QuickHire shortlist</h1>
      <input value={jobId} onChange={(e) => setJobId(e.target.value)} />
      <table>
        <thead><tr><th>Candidate</th><th>Smart Score</th><th>Status</th></tr></thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.email}>
              <td>{c.email}</td>
              <td>{Math.round(c.score * 100)}</td>
              <td>{c.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
