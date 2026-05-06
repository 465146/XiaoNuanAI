// ── 仪表盘逻辑 ──
let _moodChart = null, _phq9Chart = null;

async function loadDashboard() {
  try {
    const [scoresRes, reportRes] = await Promise.all([
      authFetch("/api/mood/scores?days=30"),
      authFetch("/api/mood/report"),
    ]);
    const scoresData = await scoresRes.json();
    const reportData = await reportRes.json();

    renderStats(scoresData.scores, scoresData.phq9_history);
    renderMoodChart(scoresData.scores);
    renderPHQ9Chart(scoresData.phq9_history);
    document.getElementById("weeklyReport").textContent = reportData.text;
  } catch (err) {
    console.error("Dashboard load error:", err);
  }
}

function renderStats(scores, phq9History) {
  if (!scores || scores.length === 0) {
    document.getElementById("statToday").textContent = "--";
    document.getElementById("statAvg").textContent = "--";
    document.getElementById("statPhq9").textContent = "--";
    return;
  }

  const last = scores[scores.length - 1];
  const lastScore = parseFloat(last.score);
  const avg = scores.reduce((s, r) => s + parseFloat(r.score), 0) / scores.length;

  document.getElementById("statToday").textContent = formatScore(lastScore);
  document.getElementById("statAvg").textContent = formatScore(avg);

  // 最新 PHQ-9
  if (phq9History && phq9History.length > 0) {
    const lastPHQ = phq9History[0];
    const sevMap = {none:'无',mild:'轻度',moderate:'中度','moderately-severe':'中重度',severe:'重度'};
    document.getElementById("statPhq9").textContent = `${lastPHQ.total_score}/27 · ${sevMap[lastPHQ.severity]||lastPHQ.severity}`;
  } else {
    document.getElementById("statPhq9").textContent = "未测试";
  }
}

function formatScore(s) {
  if (s <= 0.3) return `🟢 ${s.toFixed(2)} 良好`;
  if (s <= 0.55) return `🟡 ${s.toFixed(2)} 中等`;
  return `🔴 ${s.toFixed(2)} 需关注`;
}

function renderMoodChart(scores) {
  const el = document.getElementById("chartMood");
  if (!el) return;
  if (_moodChart) _moodChart.dispose();
  const chart = echarts.init(el);
  _moodChart = chart;

  const dates = scores.map(r => r.date);
  const values = scores.map(r => parseFloat(r.score));

  chart.setOption({
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: dates, axisLabel: { rotate: 45, fontSize: 11 } },
    yAxis: { type: "value", min: 0, max: 1, axisLabel: { formatter: v => v.toFixed(2) } },
    series: [{
      data: values, type: "line", smooth: true,
      lineStyle: { color: "#FF8C42", width: 2 },
      itemStyle: { color: "#FF8C42" },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: "rgba(255,140,66,0.3)" },
        { offset: 1, color: "rgba(255,140,66,0.02)" },
      ])},
      markLine: {
        silent: true,
        data: [
          { yAxis: 0.3, lineStyle: { color: "#7EC8A0", type: "dashed" } },
          { yAxis: 0.6, lineStyle: { color: "#E74C3C", type: "dashed" } },
        ],
      },
    }],
  });

  setTimeout(() => chart.resize(), 100);
  window.addEventListener("resize", () => chart.resize());
}

function renderPHQ9Chart(records) {
  const el = document.getElementById("chartPHQ9");
  if (!el) return;
  if (_phq9Chart) _phq9Chart.dispose();
  const chart = echarts.init(el);
  _phq9Chart = chart;

  if (!records || records.length === 0) {
    chart.setOption({
      title: { text: "暂无 PHQ-9 测试记录", left: "center", top: "center", textStyle: { color: "#999", fontSize: 14 } },
    });
    return;
  }

  const sorted = [...records].reverse();
  const dates = sorted.map(r => {
    const d = new Date(r.created_at);
    return `${d.getMonth()+1}/${d.getDate()}`;
  });
  const chartScores = sorted.map(r => r.total_score);

  chart.setOption({
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: dates },
    yAxis: { type: "value", min: 0, max: 27,
      axisLabel: { formatter: v => String(v) } },
    series: [{
      data: chartScores, type: "bar",
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: "#FF8C42" }, { offset: 1, color: "#FFC99A" },
        ]),
        borderRadius: [8, 8, 0, 0],
      },
      markLine: {
        silent: true,
        data: [
          { yAxis: 5, label: { formatter: "正常" }, lineStyle: { color: "#7EC8A0" } },
          { yAxis: 10, label: { formatter: "轻度" }, lineStyle: { color: "#F4D03F" } },
          { yAxis: 15, label: { formatter: "中度" }, lineStyle: { color: "#E67E22" } },
          { yAxis: 20, label: { formatter: "中重度" }, lineStyle: { color: "#E74C3C" } },
        ],
      },
    }],
  });

  setTimeout(() => chart.resize(), 100);
  window.addEventListener("resize", () => chart.resize());
}
