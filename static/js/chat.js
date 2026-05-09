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

  // ── 音乐播放器 (APlayer) ──
  const _embeddedSongs = new Set();
  const _pendingSongs = new Set(); // 正在加载中的 songId

  async function embedMusicPlayers(bubble) {
    if (typeof APlayer === 'undefined') return;

    // 收集 songId
    const ids = [];
    bubble.querySelectorAll('a[href*="music.163.com"]').forEach(function(a) {
      const m = a.getAttribute('href').match(/song\?id=(\d+)/);
      if (m) ids.push(m[1]);
    });
    const walker = document.createTreeWalker(bubble, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const re = /https?:\/\/music\.163\.com\/(#\/)?song\?id=(\d+)/gi;
      let m;
      while ((m = re.exec(node.textContent))) ids.push(m[2]);
    }

    for (const songId of ids) {
      if (_embeddedSongs.has(songId) || _pendingSongs.has(songId)) continue;
      _pendingSongs.add(songId);

      try {
        const resp = await fetch('/api/music/player?songId=' + songId);
        if (!resp.ok) { _pendingSongs.delete(songId); continue; }
        const song = await resp.json();
        if (!song.url) { _pendingSongs.delete(songId); continue; }

        const wrap = document.createElement('div');
        wrap.className = 'music-player';
        bubble.appendChild(wrap);

        new APlayer({
          container: wrap,
          autoplay: false,
          preload: 'metadata',
          audio: [{
            name: song.name || '未知歌曲',
            artist: song.artist || '未知歌手',
            url: song.url,
            cover: song.cover || '',
            lrc: song.lrc || ''
          }]
        });
        _embeddedSongs.add(songId);
        _pendingSongs.delete(songId);
      } catch (e) {
        _pendingSongs.delete(songId);
      }
    }
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
