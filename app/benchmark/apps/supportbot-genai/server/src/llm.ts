import OpenAI from "openai";
import { searchHelpCentre } from "./retrieval";
import { history } from "./transcripts";

const client = new OpenAI();
const MODEL = process.env.LLM_MODEL ?? "gpt-4o-mini";

const SYSTEM_PROMPT = `You are the ACME Home Energy support assistant. Answer only questions about
orders, deliveries, invoices and tariffs using the provided help-centre extracts. If you are not sure,
or the customer asks for a person, reply with HANDOVER. Never give legal or financial advice.`;

export type Reply = { text: string; model: string; handover: boolean; usage: { prompt: number; completion: number } };

export async function answer(sessionId: string, message: string): Promise<Reply> {
  const context = await searchHelpCentre(message, 4);
  const past = await history(sessionId, 12);
  const completion = await client.chat.completions.create({
    model: MODEL,
    temperature: 0.2,
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      { role: "system", content: `Help-centre extracts:\n${context.join("\n---\n")}` },
      ...past,
      { role: "user", content: message },
    ],
  });
  const text = completion.choices[0]?.message?.content ?? "";
  // TODO(SUP-88): label AI-generated replies (AI Act Art. 50(2)) once the design team has a badge.
  return {
    text: text.replace("HANDOVER", "Let me connect you with a colleague."),
    model: completion.model,
    handover: text.includes("HANDOVER"),
    usage: { prompt: completion.usage?.prompt_tokens ?? 0, completion: completion.usage?.completion_tokens ?? 0 },
  };
}
