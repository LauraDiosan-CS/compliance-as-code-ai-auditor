import React from "react";
import { Application, Reason } from "../types";
import { postDecision, postOverride } from "../api";

type Props = { applications: Application[]; onChange: () => void };

function ReasonList({ reasons }: { reasons: Reason[] }) {
  return (
    <ul className="reasons">
      {reasons.map(([feature, weight]) => (
        <li key={feature} className={weight >= 0 ? "pos" : "neg"}>
          {weight >= 0 ? "▲" : "▼"} {feature.replaceAll("_", " ")}
        </li>
      ))}
    </ul>
  );
}

export function CandidateRanking({ applications, onChange }: Props) {
  return (
    <section>
      <div className="notice" role="note">
        AI-suggested ranking. The order below is a recommendation produced by an AI model
        (ranker {applications[0]?.modelVersion ?? "n/a"}). You, the recruiter, make the final
        decision for every candidate. Use “Move” to disregard the ranking.
      </div>
      <table>
        <thead>
          <tr><th>#</th><th>Candidate</th><th>Score</th><th>Main reasons</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {applications.map((a, i) => (
            <tr key={a.id}>
              <td>{i + 1}</td>
              <td>{a.candidateRef}</td>
              <td>{a.needsManualReview ? "unranked" : a.score?.toFixed(2)}</td>
              <td><ReasonList reasons={a.reasons} /></td>
              <td>
                <button onClick={() => postDecision(a.id, "advance").then(onChange)}>Advance</button>
                <button onClick={() => postDecision(a.id, "reject").then(onChange)}>Reject…</button>
                <button onClick={() => postOverride(a.id).then(onChange)}>Move</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
