/* PrivateAI Studio frontend. One shared chat/upload pattern per mode. */
const main = document.getElementById("main");
let currentMode = "docs";
let currentChatId = null;

/* ---------- health ---------- */
fetch("/api/health").then(r => r.json()).then(h => {
  const el = document.getElementById("ollama-status");
  if (h.ollama) { el.textContent = "● Ollama connected"; el.classList.add("ok"); }
  else {
    el.textContent = "● Ollama not found — start Ollama to chat";
    el.classList.add("bad");
  }
});

/* ---------- mode switching ---------- */
document.querySelectorAll(".mode").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".mode").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    currentMode = btn.dataset.mode;
    currentChatId = null;
    render();
  });
});

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

/* ---------- shared chat panel (docs + code) ---------- */
function chatPanel(mode, title, desc, accept, uploadUrl, askUrl, docsUrl) {
  const p = el(`<div class="panel active">
    <h2>${title}</h2><div class="desc">${desc}</div>
    <div class="card"><h3>Library</h3>
      <input type="file" accept="${accept}">
      <div class="doc-list"></div>
    </div>
    <div id="chat-log"></div>
    <div class="chat-row">
      <input type="text" placeholder="Ask a question…">
      <button class="primary">Send</button>
    </div>
  </div>`);
  const fileInput = p.querySelector('input[type="file"]');
  const list = p.querySelector(".doc-list");
  const log = p.querySelector("#chat-log");
  const input = p.querySelector('input[type="text"]');
  const sendBtn = p.querySelector("button.primary");

  function refreshDocs() {
    fetch(docsUrl).then(r => r.json()).then(docs => {
      list.innerHTML = "";
      docs.forEach(d => {
        const pill = el(`<span class="doc-pill">${d.name}<button>✕</button></span>`);
        pill.querySelector("button").onclick = () => {
          fetch(`${docsUrl}/${d.id}`, { method: "DELETE" }).then(refreshDocs);
        };
        list.appendChild(pill);
      });
    });
  }
  fileInput.onchange = () => {
    const fd = new FormData();
    fd.append("file", fileInput.files[0]);
    fetch(uploadUrl, { method: "POST", body: fd })
      .then(r => r.json().then(j => ({ ok: r.ok, j })))
      .then(({ ok, j }) => {
        if (!ok) { addMsg("ai", "Error: " + (j.detail || "upload failed")); return; }
        addMsg("ai", `Added "${j.name}" (${j.chunks} chunks). Ask me anything about it.`);
        refreshDocs();
      });
    fileInput.value = "";
  };
  function addMsg(who, text) {
    const m = el(`<div class="msg ${who}"></div>`);
    m.textContent = text;
    log.appendChild(m);
    log.scrollTop = log.scrollHeight;
    return m;
  }
  async function send() {
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    addMsg("user", q);
    const ai = addMsg("ai", "…");
    try {
      const r = await fetch(askUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, chat_id: currentChatId }),
      });
      if (!r.ok) {
        const j = await r.json();
        ai.textContent = "Error: " + (j.detail || "request failed");
        ai.classList.add("error");
        return;
      }
      ai.textContent = "";
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        ai.textContent += dec.decode(value);
        log.scrollTop = log.scrollHeight;
      }
    } catch (e) {
      ai.textContent = "Error: could not reach the server.";
      ai.classList.add("error");
    }
  }
  sendBtn.onclick = send;
  input.onkeydown = e => { if (e.key === "Enter") send(); };
  refreshDocs();
  return p;
}

/* ---------- one-shot panels (resume + meetings) ---------- */
function formPanel(title, desc, fieldsHtml, url, isFile) {
  const p = el(`<div class="panel active">
    <h2>${title}</h2><div class="desc">${desc}</div>
    <div class="card">${fieldsHtml}<button class="primary">Run</button></div>
    <div class="card"><h3>Result</h3><div class="result hint">The answer streams here.</div></div>
  </div>`);
  const result = p.querySelector(".result");
  p.querySelector("button.primary").onclick = async () => {
    result.textContent = "";
    result.classList.remove("hint");
    const fd = new FormData();
    p.querySelectorAll("[data-f]").forEach(inp => {
      if (inp.type === "file") { if (inp.files[0]) fd.append(inp.dataset.f, inp.files[0]); }
      else fd.append(inp.dataset.f, inp.value);
    });
    try {
      const r = await fetch(url, { method: "POST", body: fd });
      if (!r.ok) {
        const j = await r.json();
        result.textContent = "Error: " + (j.detail || "request failed");
        return;
      }
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        result.textContent += dec.decode(value);
      }
    } catch (e) {
      result.textContent = "Error: could not reach the server.";
    }
  };
  return p;
}

/* ---------- notes panel ---------- */
function notesPanel() {
  const p = el(`<div class="panel active">
    <h2>🔒 Private Notes</h2>
    <div class="desc">AES-encrypted at rest. Your password is never stored.</div>
    <div class="card"><h3>New note</h3>
      <input type="text" data-f="title" placeholder="Title" style="margin-bottom:8px">
      <textarea data-f="content" placeholder="Write your note…"></textarea>
      <input type="password" data-f="password" placeholder="Password" style="margin-top:8px">
      <button class="primary" id="save-note">Save encrypted</button>
    </div>
    <div class="card"><h3>Your notes</h3><div id="note-list" class="hint">No notes yet.</div></div>
    <div class="card" id="open-card" style="display:none"><h3 id="open-title"></h3>
      <input type="password" id="open-pw" placeholder="Password to unlock">
      <button class="primary" id="open-btn">Unlock</button>
      <div class="result" id="open-body" style="margin-top:10px"></div>
    </div>
  </div>`);
  const list = p.querySelector("#note-list");
  function refresh() {
    fetch("/api/notes").then(r => r.json()).then(notes => {
      list.innerHTML = "";
      list.classList.remove("hint");
      if (!notes.length) { list.textContent = "No notes yet."; list.classList.add("hint"); return; }
      notes.forEach(n => {
        const item = el(`<div class="note-item">${n.title}</div>`);
        item.onclick = () => {
          p.querySelector("#open-card").style.display = "block";
          p.querySelector("#open-title").textContent = n.title;
          p.querySelector("#open-body").textContent = "";
          p.querySelector("#open-btn").onclick = () => {
            const pw = p.querySelector("#open-pw").value;
            fetch(`/api/notes/${n.id}/open`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ password: pw }),
            }).then(r => r.json().then(j => ({ ok: r.ok, j })))
              .then(({ ok, j }) => {
                p.querySelector("#open-body").textContent =
                  ok ? j.content : "Error: " + (j.detail || "cannot open");
              });
          };
        };
        list.appendChild(item);
      });
    });
  }
  p.querySelector("#save-note").onclick = () => {
    const title = p.querySelector('[data-f="title"]').value;
    const content = p.querySelector('[data-f="content"]').value;
    const password = p.querySelector('[data-f="password"]').value;
    fetch("/api/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, content, password }),
    }).then(r => r.json().then(j => ({ ok: r.ok, j })))
      .then(({ ok, j }) => {
        if (!ok) { alert("Error: " + (j.detail || "save failed")); return; }
        p.querySelector('[data-f="title"]').value = "";
        p.querySelector('[data-f="content"]').value = "";
        p.querySelector('[data-f="password"]').value = "";
        refresh();
      });
  };
  refresh();
  return p;
}

/* ---------- render ---------- */
function render() {
  main.innerHTML = "";
  if (currentMode === "docs") {
    main.appendChild(chatPanel("docs", "📄 Documents",
      "Upload PDFs or text files, then chat with them. Answers cite their sources.",
      ".pdf,.txt,.md", "/api/docs/upload", "/api/docs/ask", "/api/docs/documents"));
  } else if (currentMode === "code") {
    main.appendChild(chatPanel("code", "💻 Codebase",
      "Upload a zip of a codebase, then ask where things live and how they work.",
      ".zip", "/api/code/upload", "/api/code/ask", "/api/code/documents"));
  } else if (currentMode === "resume") {
    main.appendChild(formPanel("🎯 Resume Coach",
      "Honest, offline feedback on your CV against a job description.",
      `<input type="file" data-f="cv" accept=".pdf,.txt,.md" style="margin-bottom:8px">
       <textarea data-f="job_description" placeholder="Paste the job description here…"></textarea>`,
      "/api/resume/analyze"));
  } else if (currentMode === "meetings") {
    main.appendChild(formPanel("🎙️ Meetings",
      "Turn a transcript into a summary, decisions, and action items.",
      `<input type="file" data-f="file" accept=".txt,.md" style="margin-bottom:8px">
       <textarea data-f="transcript" placeholder="Or paste the transcript here…"></textarea>`,
      "/api/meetings/summarize"));
  } else if (currentMode === "notes") {
    main.appendChild(notesPanel());
  }
}
render();
