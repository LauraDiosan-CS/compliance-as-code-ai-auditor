import express from "express";
import rateLimit from "express-rate-limit";
import helmet from "helmet";
import { loadConfig } from "./config";
import { answer } from "./llm";
import { logLlmCall } from "./logging";
import { requireAdmin, sessionAuth } from "./auth";
import { appendMessage, deleteCustomerData, exportTranscript, startRetentionJob } from "./transcripts";

const cfg = loadConfig();
const app = express();
app.use(helmet());
app.use(express.json({ limit: "16kb" }));

// /api/chat is declared public in config/app.yaml (public_endpoints)
const chatLimiter = rateLimit({
  windowMs: 60_000,
  limit: cfg.rate_limit.chat_per_minute,
  keyGenerator: (req) => req.header("x-session-id") ?? req.ip ?? "anon",
});

app.post("/api/chat", chatLimiter, sessionAuth, async (req, res) => {
  const { sessionId, customerId } = res.locals;
  const text = String(req.body.message ?? "").slice(0, 2000);
  await appendMessage(sessionId, customerId, "user", text);
  const started = Date.now();
  const reply = await answer(sessionId, text);
  logLlmCall({ sessionId, model: reply.model, promptTokens: reply.usage.prompt, completionTokens: reply.usage.completion, latencyMs: Date.now() - started, handover: reply.handover });
  await appendMessage(sessionId, customerId, "assistant", reply.text);
  res.json({ reply: reply.text, handover: reply.handover });
});

app.get("/admin/transcripts/:customerId", requireAdmin, async (req, res) => {
  res.json(await exportTranscript(req.params.customerId));
});

app.delete("/admin/customers/:customerId/data", requireAdmin, async (req, res) => {
  // data subject erasure request (ticket from the privacy team)
  await deleteCustomerData(req.params.customerId);
  res.status(204).end();
});

startRetentionJob(cfg.retention.transcript_days);
app.listen(cfg.port, () => console.info(`supportbot listening on ${cfg.port}`));
