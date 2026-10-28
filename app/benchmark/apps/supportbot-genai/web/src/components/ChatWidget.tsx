import React, { useState } from "react";
import { sendMessage } from "../api";

type Msg = { from: "user" | "bot"; text: string };

export function ChatWidget() {
  const [messages, setMessages] = useState<Msg[]>([
    { from: "bot", text: "Hi! How can I help you with your order or tariff today?" },
  ]);
  const [draft, setDraft] = useState("");

  async function submit() {
    const text = draft.trim();
    if (!text) return;
    setDraft("");
    setMessages((m) => [...m, { from: "user", text }]);
    const { reply } = await sendMessage(text);
    setMessages((m) => [...m, { from: "bot", text: reply }]);
  }

  return (
    <aside className="chat">
      <header>
        <strong>ACME Support</strong>
        <p className="disclosure">
          You are chatting with an AI assistant. It can make mistakes; ask for a human agent at any time.
          See our <a href="/privacy#support-chat">privacy notice</a>.
        </p>
      </header>
      <ol className="messages">
        {messages.map((m, i) => (
          <li key={i} className={m.from}>{m.text}</li>
        ))}
      </ol>
      <footer>
        <input value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} />
        <button onClick={submit}>Send</button>
      </footer>
    </aside>
  );
}
