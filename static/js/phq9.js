// ── PHQ-9 逻辑 ──
let phq9SessionId = null;

document.getElementById("startPHQ9").addEventListener("click", async () => {
  try {
    const res = await authFetch("/api/phq9/start", { method: "POST" });
    const data = await res.json();
    phq9SessionId = data.session_id;

    document.getElementById("phq9Intro").style.display = "none";
    document.getElementById("phq9Result").style.display = "none";
    document.getElementById("phq9Question").style.display = "block";

    showQuestion(data);
  } catch (err) {
    alert("启动测试失败: " + err.message);
  }
});

function showQuestion(data) {
  document.getElementById("phq9Num").textContent = `第 ${data.current}/${data.total} 题`;
  document.getElementById("phq9Text").textContent = data.question;
  document.getElementById("phq9Progress").style.width = `${((data.current - 1) / data.total) * 100}%`;

  const optionsEl = document.getElementById("phq9Options");
  optionsEl.innerHTML = data.options.map((opt, i) => `
    <button class="option-btn" data-value="${i}">${i} — ${opt}</button>
  `).join("");

  optionsEl.querySelectorAll(".option-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const value = parseInt(btn.dataset.value);
      try {
        const res = await authFetch("/api/phq9/answer", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: phq9SessionId, answer: value }),
        });
        const result = await res.json();

        if (result.completed) {
          document.getElementById("phq9Question").style.display = "none";
          document.getElementById("phq9Result").style.display = "block";
          showResult(result);
          loadPHQ9History();
        } else {
          showQuestion(result);
        }
      } catch (err) {
        alert("提交失败: " + err.message);
      }
    });
  });
}

function showResult(data) {
  const sevMap = {
    none: ["无显著症状", "sev-none"],
    mild: ["轻度困扰", "sev-mild"],
    moderate: ["中度困扰", "sev-moderate"],
    "moderately-severe": ["中重度困扰", "sev-moderately-severe"],
    severe: ["重度困扰", "sev-severe"],
  };
  const [sevLabel, sevClass] = sevMap[data.severity] || ["未知", ""];

  document.getElementById("phq9ResultCard").innerHTML = `
    <h3>📊 测试完成</h3>
    <div class="result-severity ${sevClass}">${sevLabel}</div>
    <p style="margin-bottom:16px;line-height:1.8;">${data.feedback.replace(/\n/g, "<br>")}</p>
    <button class="btn-primary" onclick="location.reload()">重新测试</button>
  `;
}

async function loadPHQ9History() {
  try {
    const res = await authFetch("/api/phq9/history");
    const data = await res.json();
    const el = document.getElementById("phq9HistoryList");

    if (!data.records || data.records.length === 0) {
      el.innerHTML = '<p class="empty-hint">暂无测试记录</p>';
      return;
    }

    el.innerHTML = data.records.map(r => {
      const sevMap = {
        none: "无显著", mild: "轻度", moderate: "中度",
        "moderately-severe": "中重度", severe: "重度",
      };
      const d = new Date(r.created_at);
      const dateStr = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")} ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`;
      return `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--border);font-size:14px;">
          <span>${dateStr}</span>
          <span>总分 <strong>${r.total_score}</strong> / 27 · ${sevMap[r.severity] || r.severity}</span>
        </div>
      `;
    }).join("");
  } catch (err) {
    console.error("PHQ-9 history load error:", err);
  }
}
