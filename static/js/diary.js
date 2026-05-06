// ── 日记逻辑 ──
async function loadDiaryList() {
  try {
    const res = await authFetch("/api/diary/list");
    const data = await res.json();
    const listEl = document.getElementById("diaryList");

    if (!data.entries || data.entries.length === 0) {
      listEl.innerHTML = '<p class="empty-hint">还没有日记，<br>点击右上角"生成今日日记"吧</p>';
      return;
    }

    listEl.innerHTML = data.entries.map((e, i) => `
      <div class="diary-item ${i === 0 ? 'active' : ''}" data-date="${e.date}">
        <div class="diary-date">${e.date}</div>
        <div class="diary-mood">${e.mood || '日常'}</div>
        <div class="diary-preview">${e.preview || ''}</div>
      </div>
    `).join("");

    listEl.querySelectorAll(".diary-item").forEach(item => {
      item.addEventListener("click", async () => {
        listEl.querySelectorAll(".diary-item").forEach(i => i.classList.remove("active"));
        item.classList.add("active");
        try {
          const date = item.dataset.date;
          const detailRes = await authFetch(`/api/diary/${date}`);
          if (detailRes.ok) {
            const detailData = await detailRes.json();
            renderDiaryDetail(detailData.entry);
          }
        } catch (e) {
          console.error("Diary detail error:", e);
        }
      });
    });

    // 默认加载第一篇
    try {
      const first = data.entries[0];
      const detailRes = await authFetch(`/api/diary/${first.date}`);
      if (detailRes.ok) {
        const detailData = await detailRes.json();
        renderDiaryDetail(detailData.entry);
      }
    } catch (e) {
      console.error("Detail load error:", e);
    }
  } catch (err) {
    console.error("Diary load error:", err);
    document.getElementById("diaryList").innerHTML = '<p class="empty-hint">加载失败，请稍后重试</p>';
  }
}

let _currentEntry = null;

function renderDiaryDetail(entry) {
  const el = document.getElementById("diaryDetail");
  const actions = document.getElementById("diaryActions");
  if (!entry) {
    el.innerHTML = '<p class="empty-hint">暂无内容</p>';
    actions.style.display = 'none';
    _currentEntry = null;
    return;
  }
  _currentEntry = entry;
  el.innerHTML = `
    <h3>📝 ${entry.date}</h3>
    <div class="diary-meta">心情标签：${entry.mood || '日常'}</div>
    <div class="diary-body">${entry.content}</div>
  `;
  actions.style.display = 'flex';
}

// 生成日记按钮
document.getElementById("genDiary").addEventListener("click", async () => {
  const btn = document.getElementById("genDiary");
  btn.disabled = true;
  btn.textContent = "生成中...";

  try {
    const res = await authFetch("/api/diary/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: "" }),
    });
    const data = await res.json();
    if (data.entry) {
      alert("日记生成成功！");
      loadDiaryList();
    } else {
      alert(data.message || "生成失败，请稍后重试");
    }
  } catch (err) {
    alert("生成失败: " + err.message);
  }

  btn.disabled = false;
  btn.textContent = "✨ 生成今日日记";
});

// 下载日记
document.getElementById("downloadDiary").addEventListener("click", () => {
  if (!_currentEntry) return;
  const fmt = document.getElementById("downloadFormat").value;
  const date = _currentEntry.date;
  const mood = _currentEntry.mood || '日常';
  const content = _currentEntry.content || '';

  let text, ext, mime;
  if (fmt === 'md') {
    ext = 'md'; mime = 'text/markdown';
    text = `# 📝 情绪日记 · ${date}\n\n**心情：** ${mood}\n\n---\n\n${content}\n`;
  } else {
    ext = 'txt'; mime = 'text/plain';
    text = `情绪日记 · ${date}\n心情：${mood}\n\n${content}`;
  }

  const blob = new Blob([text], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `情绪日记_${date}.${ext}`;
  a.click();
  URL.revokeObjectURL(url);
});
