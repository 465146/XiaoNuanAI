// ── 聊天逻辑 ──
(function () {
  const messagesEl = document.getElementById("chatMessages");
  const inputEl = document.getElementById("chatInput");
  const sendBtn = document.getElementById("sendBtn");
  const clearBtn = document.getElementById("clearChat");

  let loading = false;
  let historyLoaded = false;

  function scrollBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // ── 音乐播放器 ──
  // 已嵌入的歌曲 ID 集合，避免重复创建播放器
  const _embeddedSongs = new Set();

  function buildAudioPlayer(songId) {
    if (_embeddedSongs.has(songId)) return null;
    _embeddedSongs.add(songId);
    const wrap = document.createElement('div');
    wrap.className = 'music-player';
    wrap.innerHTML =
      '<audio controls preload="metadata" src="/api/music/stream?songId=' + songId + '" ' +
      'style="width:100%;height:40px;border-radius:8px;outline:none;">' +
      '</audio>' +
      '<a href="https://music.163.com/#/song?id=' + songId + '" target="_blank" ' +
      'style="font-size:12px;color:#999;">🎵 在网易云中打开</a>';
    return wrap;
  }

  function embedMusicPlayers(bubble) {
    // 收集所有 song ID（从 <a> 标签 + 纯文本）
    const ids = [];
    // 1) <a> 标签
    bubble.querySelectorAll('a[href*="music.163.com"]').forEach(function(a) {
      const m = a.getAttribute('href').match(/song\?id=(\d+)/);
      if (m) ids.push(m[1]);
    });
    // 2) 纯文本兜底
    const walker = document.createTreeWalker(bubble, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const re = /https?:\/\/music\.163\.com\/(#\/)?song\?id=(\d+)/gi;
      let m;
      while ((m = re.exec(node.textContent)) !== null) {
        ids.push(m[2]);
      }
    }
    // 在 bubble 底部插入播放器
    ids.forEach(function(id) {
      const player = buildAudioPlayer(id);
      if (player) bubble.appendChild(player);
    });
  }

  function addBubble(role, text) {
    const div = document.createElement("div");
    div.className = 'chat-bubble ' + role;
    if (role === "assistant") {
      div.innerHTML = marked.parse(text);
      embedMusicPlayers(div);
    } else {
      div.textContent = text;
    }
    messagesEl.appendChild(div);
    scrollBottom();
    return div;
  }

  let lastMsgCount = 0;

  function showWelcome() {
    messagesEl.innerHTML = '<div class="chat-welcome"><div class="welcome-emoji">🫧</div><h3>嗨，我是小暖 👋</h3><p>一个温暖的 AI 心理陪伴伙伴。<br>无论你想聊什么，我都在这里倾听。</p><p class="welcome-hint">今天感觉怎么样？</p></div>';
  }

  async function loadHistory() {
    try {
      const res = await authFetch("/api/chat/history?limit=200");
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (!data.messages || data.messages.length === 0) {
        showWelcome();
        lastMsgCount = 0;
        return;
      }
      const cnt = data.messages.length;
      if (cnt === lastMsgCount && historyLoaded) return;
      lastMsgCount = cnt;
      messagesEl.innerHTML = '';
      for (const m of data.messages) {
        addBubble(m.role, m.content);
      }
    } catch (err) {
      if (!historyLoaded) {
        showWelcome();
      }
    }
    historyLoaded = true;
  }

  loadHistory();

  // 每 3 秒检查新消息（微信同步）
  setInterval(loadHistory, 3000);

  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || loading) return;
    inputEl.value = "";
    loading = true;
    sendBtn.disabled = true;

    addBubble("user", text);
    const assistantBubble = addBubble("assistant", "");
    assistantBubble.innerHTML = "<em>思考中...</em>";

    try {
      const response = await authFetch("/api/chat/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let reply = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") continue;
            reply += data;
            assistantBubble.innerHTML = marked.parse(reply);
            embedMusicPlayers(assistantBubble);
            scrollBottom();
          }
        }
      }

      if (!reply) assistantBubble.innerHTML = "（小暖正在沉思...请再试一次）";
    } catch (err) {
      assistantBubble.innerHTML = "连接出错了，请稍后重试 😢";
      console.error(err);
    }

    lastMsgCount += 2;
    loading = false;
    sendBtn.disabled = false;
    inputEl.focus();
  }

  sendBtn.addEventListener("click", sendMessage);
  inputEl.addEventListener("keydown", function(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  clearBtn.addEventListener("click", async function() {
    if (!confirm("确定要清空对话历史吗？")) return;
    await authFetch("/api/chat/clear", { method: "POST" });
    historyLoaded = true;
    showWelcome();
  });
})();
