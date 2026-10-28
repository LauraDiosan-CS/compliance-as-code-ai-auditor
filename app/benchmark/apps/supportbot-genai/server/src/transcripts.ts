import { Pool } from "pg";

const pool = new Pool({ connectionString: process.env.DATABASE_URL, ssl: { rejectUnauthorized: true } });

export async function appendMessage(sessionId: string, customerId: string | null, role: string, content: string) {
  // full message text is stored as typed by the customer (may include e-mail, phone, address)
  await pool.query(
    "INSERT INTO transcript_messages (session_id, customer_id, role, content, created_at) VALUES ($1,$2,$3,$4,now())",
    [sessionId, customerId, role, content],
  );
}

export async function history(sessionId: string, n: number) {
  const { rows } = await pool.query(
    "SELECT role, content FROM transcript_messages WHERE session_id=$1 ORDER BY created_at DESC LIMIT $2",
    [sessionId, n],
  );
  return rows.reverse();
}

export async function exportTranscript(customerId: string) {
  const { rows } = await pool.query("SELECT * FROM transcript_messages WHERE customer_id=$1 ORDER BY created_at", [customerId]);
  return rows;
}

export async function deleteCustomerData(customerId: string) {
  await pool.query("DELETE FROM transcript_messages WHERE customer_id=$1", [customerId]);
  await pool.query("DELETE FROM chat_sessions WHERE customer_id=$1", [customerId]);
}

/** Transcripts are kept for quality assurance and dispute handling, then purged nightly. */
export function startRetentionJob(days: number) {
  const purge = () =>
    pool.query("DELETE FROM transcript_messages WHERE created_at < now() - ($1 || ' days')::interval", [days]);
  setInterval(purge, 24 * 3600 * 1000);
}
