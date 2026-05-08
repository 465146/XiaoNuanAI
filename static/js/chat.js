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

  // 检测网易云音乐链接，自动嵌入 iframe 播放器
  function embedMusicPlayers(bubble) {
    // 1) 查找 markdown 生成的 <a> 标签
    const links = bubble.querySelectorAll('a[href*="music.163.com"]');
    links.forEach(function(link) {
      embedFromUrl(link.getAttribute('href'), link);
    });
    // 2) 兜底：扫描纯文本中的 music.163.com 网址（marked 不自动链接纯文本 URL）
    const walker = document.createTreeWalker(bubble, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    textNodes.forEach(function(node) {
      const re = /https?:\/\/music\.163\.com\/(#\/)?(song|playlist)\?id=(\d+)/gi;
      let m;
      while ((m = re.exec(node.textContent)) !== null) {
        const type = m[2] === 'playlist' ? 0 : 2;
        const id = m[3];
        const wrapper = document.createElement('span');
        wrapper.innerHTML =
          '<iframe class="music-player" frameborder="0" width="100%" ' +
          (type === 0 ? 'height="450" ' : 'height="86" ') +
          'src="https://music.163.com/outchain/player?type=' + type + '&id=' + id + '&auto=0&height=' + (type === 0 ? '430' : '66') + '">' +
          '</iframe>';
        node.parentNode.insertBefore(wrapper, node.nextSibling);
      }
    });
  }

  function embedFromUrl(href, afterNode) {
    let m = href.match(/song\?id=(\d+)/);
    if (m) {
      const iframe = document.createElement('iframe');
      iframe.className = 'music-player';
      iframe.src = 'https://music.163.com/outchain/player?type=2&id=' + m[1] + '&auto=0&height=66';
      iframe.setAttribute('frameborder', '0');
      iframe.setAttribute('width', '100%');
      iframe.setAttribute('height', '86');
      afterNode.insertAdjacentElement('afterend', iframe);
      return;
    }
    m = href.match(/playlist\?id=(\d+)/);
    if (m) {
      const plFrame = document.createElement('iframe');
      plFrame.className = 'music-player';
      plFrame.src = 'https://music.163.com/outchain/player?type=0&id=' + m[1] + '&auto=0&height=430';
      plFrame.setAttribute('frameborder', '0');
      plFrame.setAttribute('width', '100%');
      plFrame.setAttribute('height', '450');
      afterNode.insertAdjacentElement('afterend', plFrame);
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
