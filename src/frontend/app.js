const messages = document.getElementById("messages");
const composer = document.getElementById("composer");
const queryInput = document.getElementById("query");
const sendButton = document.getElementById("send");
let history = [];

function escapeHtml(value) {
  return value.replace(/[&<>\"]/g, (char) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;"}[char]));
}

function renderMarkdown(value) {
  let html = escapeHtml(value);
  html = html.replace(/^### (.*)$/gm, "<h3>$1</h3>")
    .replace(/^## (.*)$/gm, "<h2>$1</h2>")
    .replace(/^# (.*)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/^[-*] (.*)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br>");
  return `<p>${html}</p>`;
}

function addMessage(role, text = "") {
  document.querySelector(".welcome")?.remove();
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;
  wrapper.innerHTML = `<div class="avatar">${role === "user" ? "شما" : "AI"}</div><div class="message-body"></div>`;
  wrapper.querySelector(".message-body").innerHTML = role === "assistant" ? renderMarkdown(text) : escapeHtml(text);
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
  return wrapper.querySelector(".message-body");
}

function addSources(sources) {
  if (!sources.length) return;
  const wrapper = document.createElement("details");
  wrapper.className = "sources-panel";
  const items = sources.map((item) => {
    const excerpt = item.content.replace(/\s+/g, " ").trim();
    const preview = excerpt.length > 420 ? `${excerpt.slice(0, 420)}…` : excerpt;
    return `<li><code>${escapeHtml(item.source)}</code><p>${escapeHtml(preview)}</p></li>`;
  }).join("");
  wrapper.innerHTML = `<summary>منابع واکشی‌شده از دانش‌نامه (${sources.length})</summary><ol>${items}</ol>`;
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
}

async function sendQuery(query) {
  const userText = query.trim();
  if (!userText) return;
  addMessage("user", userText);
  const assistantBody = addMessage("assistant");
  assistantBody.innerHTML = '<span class="tool-status">در حال فکر کردن...</span>';
  queryInput.value = "";
  queryInput.disabled = true;
  sendButton.disabled = true;
  try {
    const response = await fetch("/stream", { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({query: userText, history}) });
    if (!response.ok) throw new Error(await response.text());
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let answer = "";
    let sources = [];
    while (true) {
      const {value, done} = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), {stream: !done});
      const events = buffer.split("\n\n");
      buffer = events.pop();
      for (const event of events) {
        const line = event.split("\n").find((item) => item.startsWith("data: "));
        if (!line) continue;
        const data = JSON.parse(line.slice(6));
        if (data.type === "tool_start") assistantBody.innerHTML = '<span class="tool-status">در حال جست‌وجو در دانش‌نامه...</span>';
        if (data.type === "tool_finished") assistantBody.innerHTML = '<span class="tool-status">در حال آماده‌سازی پاسخ...</span>';
        if (data.type === "sources") sources = data.sources || [];
        if (data.type === "token") { answer += data.text; assistantBody.innerHTML = renderMarkdown(answer); }
        if (data.type === "error") throw new Error(data.message);
      }
      messages.scrollTop = messages.scrollHeight;
      if (done) break;
    }
    addSources(sources);
    history.push({role: "user", content: userText}, {role: "model", content: answer});
  } catch (error) {
    assistantBody.innerHTML = `<p><strong>خطا:</strong> ${escapeHtml(error.message)}</p>`;
  } finally {
    queryInput.disabled = false;
    sendButton.disabled = false;
    queryInput.focus();
  }
}

composer.addEventListener("submit", (event) => { event.preventDefault(); sendQuery(queryInput.value); });
document.getElementById("new-chat").addEventListener("click", () => { history = []; location.reload(); });
document.querySelectorAll(".suggestions button").forEach((button) => button.addEventListener("click", () => sendQuery(button.textContent)));
queryInput.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); composer.requestSubmit(); } });
