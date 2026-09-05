// Vanilla JS, no build step, no framework - shared across all pages.
// Each page's own <script> block calls one of the init*() functions below.

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------------- artifact modal (used from Meeting Room + Reports) ---------------- */

function openArtifactModal(title, content) {
  document.getElementById("artifact-modal-title").textContent = title;
  document.getElementById("artifact-modal-content").textContent = content;
  document.getElementById("artifact-modal-backdrop").style.display = "block";
}
function closeArtifactModal() {
  const el = document.getElementById("artifact-modal-backdrop");
  if (el) el.style.display = "none";
}

async function fetchAllArtifacts(runId) {
  try {
    const manifest = await fetchJSON(`/api/meetings/${runId}/artifacts`);
    const list = manifest.files.map((f) =>
      `<li><a href="#" onclick="loadArtifactFile('${runId}','${f.path}'); return false;">${escapeHtml(f.path)}</a> <span class="hint">(${f.size_bytes}b)</span></li>`
    ).join("");
    openArtifactModal("Toàn bộ artifact", "");
    document.getElementById("artifact-modal-content").innerHTML = `<ul class="observer-list">${list}</ul>`;
  } catch (err) {
    openArtifactModal("Toàn bộ artifact", "Không tải được manifest: " + err.message);
  }
}

/* ---------------- Dashboard: Run Demo Meeting ---------------- */

async function runDemoMeeting(btn) {
  const errEl = document.getElementById("run-demo-error");
  errEl.textContent = "";
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = "Đang khởi động demo…";
  try {
    const result = await fetchJSON("/api/meetings/demo", { method: "POST" });
    window.location.href = `/meetings/${result.run_id}`;
  } catch (err) {
    errEl.textContent = "Không khởi động được demo: " + err.message;
    btn.disabled = false;
    btn.textContent = original;
  }
}

async function runDemoMeetingExtended(btn) {
  const errEl = document.getElementById("run-demo-error");
  errEl.textContent = "";
  btn.disabled = true;
  const original = btn.textContent;
  btn.textContent = "Đang khởi động demo 10 vòng…";
  try {
    const result = await fetchJSON("/api/meetings/demo-extended", { method: "POST" });
    window.location.href = `/meetings/${result.run_id}`;
  } catch (err) {
    errEl.textContent = "Không khởi động được demo 10 vòng: " + err.message;
    btn.disabled = false;
    btn.textContent = original;
  }
}

async function loadArtifactFile(runId, path) {
  try {
    const file = await fetchJSON(`/api/meetings/${runId}/artifacts/file?path=${encodeURIComponent(path)}`);
    openArtifactModal(path, file.content);
  } catch (err) {
    openArtifactModal(path, "Không tải được: " + err.message);
  }
}

/* ==================================================================
   New Council Session page
   ================================================================== */

document.addEventListener("click", function (e) {
  const chip = e.target.closest(".provider-chip");
  if (chip && !chip.classList.contains("disabled")) {
    document.querySelectorAll(".provider-chip").forEach((c) => c.classList.remove("selected"));
    chip.classList.add("selected");
    const modelInput = document.getElementById("model_override");
    if (modelInput) {
      const defaultModel = chip.dataset.defaultModel;
      modelInput.placeholder = defaultModel ? `Default: ${defaultModel}` : "mock has no model";
    }
  }
  if (chip && chip.classList.contains("disabled")) {
    document.getElementById("provider-reason").textContent = chip.title;
  }

  const tag = e.target.closest(".skill-tags[data-role] .skill-tag");
  if (tag) {
    tag.classList.toggle("on");
    const group = tag.closest(".skill-tags");
    if (group && window.COUNCIL_ROLE_SKILLS) {
      window.COUNCIL_ROLE_SKILLS[group.dataset.role] = Array.from(group.querySelectorAll(".skill-tag.on")).map((t) => t.dataset.skill);
    }
  }
});

const startBtn = document.getElementById("start-meeting-btn");
if (startBtn) {
  startBtn.addEventListener("click", async function () {
    const briefText = document.getElementById("brief_text").value.trim();
    const errEl = document.getElementById("start-meeting-error");
    errEl.textContent = "";
    if (!briefText) {
      errEl.textContent = "Đề bài không được để trống.";
      return;
    }
    const selectedChip = document.querySelector(".provider-chip.selected");
    const provider = selectedChip ? selectedChip.dataset.provider : "mock";
    const modelOverride = document.getElementById("model_override").value.trim() || null;
    const playback = document.getElementById("playback_enabled").checked;
    const roundsInput = document.querySelector('input[name="rounds"]:checked');
    const rounds = roundsInput ? parseInt(roundsInput.value, 10) : 10;

    startBtn.disabled = true;
    startBtn.textContent = "Đang khởi động…";
    try {
      const result = await fetchJSON("/api/meetings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          brief_text: briefText,
          brief_name: "session",
          provider: provider,
          model: modelOverride,
          role_skills: window.COUNCIL_ROLE_SKILLS || {},
          playback_enabled: playback,
          rounds: rounds,
        }),
      });
      window.location.href = `/meetings/${result.run_id}`;
    } catch (err) {
      errEl.textContent = "Không khởi động được cuộc họp: " + err.message;
      startBtn.disabled = false;
      startBtn.textContent = "Bắt đầu họp";
    }
  });
}

/* ==================================================================
   Meeting Room page
   ================================================================== */

const EVENT_TYPE_ICON = {
  problem_understanding: "🧭",
  proposal: "📝",
  agreement: "🤝",
  disagreement: "⚔️",
  proposed_change: "🔁",
  risk: "⚠️",
  critique: "🕵️",
  alternative: "🔀",
  defense: "🛡️",
  mind_change: "💡",
  premortem: "☠️",
  convergence: "🧩",
  decision: "✅",
};

function renderEventCard(ev) {
  const icon = EVENT_TYPE_ICON[ev.type] || "💬";
  const details = (ev.details || []).slice(0, 6).map((d) => `<li>${escapeHtml(d)}</li>`).join("");
  return `
    <div class="event-card type-${ev.type}">
      <div class="event-head">
        <span class="event-speaker">${icon} ${escapeHtml(ev.speaker_name)}${ev.target_name ? " → " + escapeHtml(ev.target_name) : ""}</span>
        <span class="event-order">R${ev.round} · #${ev.order}</span>
      </div>
      <div class="event-title">${escapeHtml(ev.title)}</div>
      <div class="event-text">${escapeHtml(ev.text)}</div>
      ${details ? `<ul class="event-details">${details}</ul>` : ""}
    </div>`;
}

function initMeetingRoom(runId) {
  let currentFilter = "all";

  document.querySelectorAll(".filter-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".filter-chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      currentFilter = chip.dataset.filter;
      refreshTranscript();
    });
  });

  document.querySelectorAll(".seat").forEach((seat) => {
    seat.addEventListener("click", async () => {
      const role = seat.dataset.role;
      try {
        const r1 = await fetchJSON(`/api/meetings/${runId}/artifacts/file?path=agents/round1/${role}.json`);
        let content = "--- Round 1 proposal ---\n" + r1.content;
        try {
          const r4 = await fetchJSON(`/api/meetings/${runId}/artifacts/file?path=agents/round4/${role}.json`);
          content += "\n\n--- Round 4 defense/revision ---\n" + r4.content;
        } catch (e) { /* devils_advocate has no round4 file - fine */ }
        openArtifactModal(role, content);
      } catch (err) {
        openArtifactModal(role, "Could not load artifact: " + err.message);
      }
    });
  });

  let roundStepsRendered = null; // total_rounds we last rendered chips for - only rebuild DOM if it changes

  function renderRoundSteps(status) {
    if (roundStepsRendered === status.total_rounds) return;
    const container = document.getElementById("round-steps");
    const labels = status.round_labels || {};
    const chips = [];
    for (let r = 1; r <= status.total_rounds; r++) {
      chips.push(`<div class="round-step" data-round="${r}">R${r} · ${escapeHtml(labels[String(r)] || "")}</div>`);
    }
    container.innerHTML = chips.join("");
    roundStepsRendered = status.total_rounds;
  }

  async function refreshStatus() {
    const status = await fetchJSON(`/api/meetings/${runId}/status`);
    if (!status.is_meeting) return status;

    renderRoundSteps(status);
    document.querySelectorAll(".round-step").forEach((el) => {
      const r = parseInt(el.dataset.round, 10);
      el.classList.remove("current", "done");
      if (r < status.current_round) el.classList.add("done");
      else if (r === status.current_round) el.classList.add("current");
    });
    document.getElementById("stat-mind-changes").textContent = status.mind_changes_count;
    document.getElementById("stat-accepted").textContent = status.accepted_count;
    document.getElementById("stat-rejected").textContent = status.rejected_count;
    document.getElementById("stat-unresolved").textContent = status.unresolved_count;

    const metaStatus = document.getElementById("meta-status");
    if (metaStatus) metaStatus.textContent = status.status === "completed" ? "hoàn tất" : "đang chạy";
    const metaElapsed = document.getElementById("meta-elapsed");
    if (metaElapsed) metaElapsed.textContent = status.elapsed_seconds != null ? `${status.elapsed_seconds}s` : "-";
    const metaProvider = document.getElementById("meta-provider");
    if (metaProvider && status.provider) metaProvider.textContent = status.provider;
    const metaModel = document.getElementById("meta-model");
    if (metaModel) metaModel.textContent = status.model || "mặc định";

    // "Devil's Advocate" round highlights with the critique color regardless
    // of which round number it is (round 3 in the 5-round pipeline, round 5
    // in the 10-round one) - matched by label, not a hardcoded round number.
    const isDevilsAdvocateRound = (status.current_round_label || "").includes("Devil's Advocate");
    document.querySelectorAll(".seat").forEach((seat) => {
      seat.classList.remove("speaking", "spoke", "critiquing", "waiting");
      const statusEl = seat.querySelector(".seat-status");
      if (seat.dataset.role === status.current_speaker_role) {
        seat.classList.add(isDevilsAdvocateRound ? "critiquing" : "speaking");
        statusEl.textContent = isDevilsAdvocateRound ? "đang phản biện…" : "đang phát biểu…";
      } else if (status.current_round > 1 || status.revealed_events > 0) {
        seat.classList.add("spoke");
        statusEl.textContent = "đã phát biểu";
      } else {
        seat.classList.add("waiting");
        statusEl.textContent = "đang chờ";
      }
    });
    return status;
  }

  async function refreshTranscript() {
    const t = await fetchJSON(`/api/meetings/${runId}/transcript?filter=${currentFilter}`);
    const scroll = document.getElementById("transcript-scroll");
    if (!t.events.length) {
      scroll.innerHTML = '<p class="hint">No events yet for this filter.</p>';
      return;
    }
    const atBottom = scroll.scrollTop + scroll.clientHeight >= scroll.scrollHeight - 40;
    scroll.innerHTML = t.events.map(renderEventCard).join("");
    if (atBottom) scroll.scrollTop = scroll.scrollHeight;
  }

  async function refreshObserver() {
    const s = await fetchJSON(`/api/meetings/${runId}/summary`);
    const body = document.getElementById("observer-body");
    const args = (s.major_arguments || []).slice(0, 5).map((a) => `<li>${escapeHtml(a)}</li>`).join("");
    const unresolved = (s.unresolved || []).map((u) => `<li><strong>${escapeHtml(u.topic)}</strong>: ${escapeHtml(u.rationale)}</li>`).join("");
    body.innerHTML = `
      <p><strong>Vòng ${s.current_round}/${s.total_rounds}</strong> - ${escapeHtml(s.current_round_label)} · ${s.is_complete ? "cuộc họp đã hoàn tất" : "đang diễn ra"}</p>
      <div class="section-title">Diễn biến mới nhất</div>
      <ul class="observer-list">${args || "<li>(chưa có)</li>"}</ul>
      <div class="section-title">Chưa giải quyết - cần bạn quyết định</div>
      <ul class="observer-list">${unresolved || "<li>(chưa có)</li>"}</ul>
      <div class="section-title">Tổng hợp sơ bộ</div>
      <p class="rationale">${escapeHtml(s.recommendation)}</p>
      <div class="human-flag">⚠ Cần bạn quyết định - ChatGPT/council chỉ tổng hợp, không tự quyết định thay bạn.</div>
    `;
  }

  const STATE_LABEL = { speaking: "Đang phát biểu…", thinking: "Đang suy nghĩ…", done: "Đã xong", waiting: "Đang chờ" };

  async function refreshParticipants() {
    const p = await fetchJSON(`/api/meetings/${runId}/participants`);
    const panel = document.getElementById("participant-panel");
    if (!p.participants || !p.participants.length) {
      panel.innerHTML = '<p class="hint">No participants.</p>';
      return;
    }
    panel.innerHTML = p.participants.map((role) => {
      const flags = [];
      if (role.has_mind_change) flags.push('<span title="Changed position on at least one topic">💡</span>');
      if (role.has_active_disagreement) flags.push('<span title="Involved in a disagreement">⚔️</span>');
      if (role.has_critical_risk) flags.push('<span title="Flagged a critical-severity issue">🔴</span>');
      return `
        <div class="participant-row state-${role.state}" data-role="${role.id}">
          <div class="p-avatar">${escapeHtml(role.display_name[0])}</div>
          <div>
            <div class="p-name">${escapeHtml(role.display_name)}</div>
            <div class="p-state">${STATE_LABEL[role.state] || role.state}${role.last_action ? " · " + escapeHtml(role.last_action.title) : ""}</div>
          </div>
          <div class="p-flags">${flags.join("")}</div>
        </div>`;
    }).join("");
    panel.querySelectorAll(".participant-row").forEach((row) => {
      row.addEventListener("click", () => {
        const seat = document.querySelector(`.seat[data-role="${row.dataset.role}"]`);
        if (seat) seat.click();
      });
    });
  }

  async function refreshMetrics() {
    const m = await fetchJSON(`/api/meetings/${runId}/metrics`);
    const strip = document.getElementById("metrics-strip");
    const rows = [
      ["requirements_count", "Requirements"], ["edge_cases_count", "Edge Cases"], ["risks_count", "Risks"],
      ["mind_changes_count", "Mind Changes"], ["unresolved_count", "Unresolved"],
      ["tokens_in", "Tokens In"], ["tokens_out", "Tokens Out"], ["duration_seconds", "Duration (s)"],
    ];
    const cells = rows.map(([key, label]) => `
      <div class="metric"><div class="num">${m[key] != null ? m[key] : "-"}</div><div class="label">${label}</div></div>
    `).join("");
    const costLabel = m.cost_is_proxy
      ? `<div class="metric"><div class="num">n/a</div><div class="label">Cost (mock proxy)</div></div>`
      : `<div class="metric"><div class="num">$${(m.estimated_cost_usd ?? 0).toFixed(4)}</div><div class="label">Est. Cost</div></div>`;
    strip.innerHTML = cells + costLabel;
  }

  async function tick() {
    try {
      const status = await refreshStatus();
      await refreshTranscript();
      await refreshObserver();
      await refreshParticipants();
      await refreshMetrics();
      if (status && !status.is_complete) {
        setTimeout(tick, 1500);
      }
    } catch (err) {
      console.error(err);
      setTimeout(tick, 3000);
    }
  }
  tick();
}

/* ==================================================================
   Human Decision Center page
   ================================================================== */

function initDecisionsPage(runId) {
  document.querySelectorAll(".choice-row").forEach((row) => {
    row.addEventListener("click", (e) => {
      const btn = e.target.closest(".choice-btn");
      if (!btn) return;
      row.querySelectorAll(".choice-btn").forEach((b) => b.className = "choice-btn");
      btn.classList.add("choice-btn", "selected-" + btn.dataset.choice);
    });
  });

  const form = document.getElementById("decisions-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const decisions = Array.from(document.querySelectorAll(".decision-item")).map((item) => {
      const topic = item.dataset.topic;
      const selectedBtn = item.querySelector(".choice-btn[class*='selected-']");
      const choice = selectedBtn ? selectedBtn.dataset.choice : "pending";
      const note = item.querySelector(".note-input").value;
      return { topic, human_choice: choice, note };
    });
    const msg = document.getElementById("decisions-saved-msg");
    try {
      await fetchJSON(`/api/meetings/${runId}/decisions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decisions }),
      });
      msg.textContent = "Đã lưu. final_summary_for_chatgpt.json đã được cập nhật.";
    } catch (err) {
      msg.textContent = "Lưu thất bại: " + err.message;
    }
  });
}

/* ==================================================================
   Roles & Skills page
   ================================================================== */

document.addEventListener("click", function (e) {
  const tag = e.target.closest(".skill-tags[data-role-skills] .skill-tag");
  if (tag) tag.classList.toggle("on");
});

async function saveRoleSkills(roleId) {
  const group = document.querySelector(`.skill-tags[data-role-skills="${roleId}"]`);
  const skillIds = Array.from(group.querySelectorAll(".skill-tag.on")).map((t) => t.dataset.skill);
  const statusEl = document.querySelector(`.save-status[data-status-for="${roleId}"]`);
  try {
    await fetchJSON(`/api/roles/${roleId}/skills`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role_id: roleId, skill_ids: skillIds }),
    });
    statusEl.textContent = "Saved ✓";
    setTimeout(() => (statusEl.textContent = ""), 2000);
  } catch (err) {
    statusEl.textContent = "Failed: " + err.message;
  }
}
