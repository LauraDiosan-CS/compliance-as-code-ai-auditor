import pino from "pino";

const logger = pino({ level: "info", base: { service: "supportbot" } });

export type LlmCall = {
  sessionId: string; model: string; promptTokens: number; completionTokens: number; latencyMs: number; handover: boolean;
};

/** One structured line per LLM call, shipped to Loki (retention set in config/app.yaml). */
export function logLlmCall(call: LlmCall) {
  logger.info({ event: "llm_call", ...call, model_version: call.model }, "llm reply generated");
}
