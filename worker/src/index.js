// Telegram webhook -> GitHub repository_dispatch. Only the owner's chat is accepted.
async function tg(env, method, body) {
  return fetch(`https://api.telegram.org/bot${env.TG_TOKEN}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

export default {
  async fetch(req, env) {
    if (req.method !== "POST") return new Response("ok");
    if (req.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) {
      return new Response("forbidden", { status: 403 });
    }
    const update = await req.json();
    const m = update.message;
    // always 200 so Telegram does not retry ignored updates
    if (!m || !m.text || String(m.chat.id) !== env.CHAT_ID) return new Response("ok");
    const r = await fetch(`https://api.github.com/repos/${env.REPO}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GH_PAT}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "bounce-arena-bot",
      },
      body: JSON.stringify({ event_type: "telegram", client_payload: { text: m.text.slice(0, 3000), message_id: m.message_id } }),
    });
    await tg(env, "sendMessage", {
      chat_id: env.CHAT_ID,
      reply_to_message_id: m.message_id,
      text: r.ok ? "⏳ Üzerinde çalışıyorum…" : `⚠️ GitHub tetiklenemedi (${r.status}). GitHub token süresi dolmuş olabilir.`,
    });
    return new Response("ok");
  },
};
