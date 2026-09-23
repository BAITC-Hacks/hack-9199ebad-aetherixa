"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const fields = [["context_need", "Контекст и потребность", 20], ["data_sources", "Данные и материалы", 20], ["expected_result", "Ожидаемый результат", 15], ["success_criteria", "Критерии успеха", 15], ["constraints", "Ограничения", 10], ["users", "Пользователи", 10], ["contact_format", "Связь с бизнесом", 10]];
  const levels = {draft: "Черновая", working: "Рабочая", ready: "Готовая", priority: "Приоритетная"};
  const statuses = {pending: "На рассмотрении", selected: "Выбрана бизнесом", rejected: "Отклонена"};
  const stepLabels = {locked: "Впереди", current: "В работе", review: "На проверке", done: "Подтверждено"};
  const collectionLabels = {research: "Исследование", plan: "План", prototype: "Прототип", verification: "Проверка", result: "Результат"};
  const safeRead = (key) => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  const safeWrite = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };
  const state = {tasks: [], drafts: [], teams: [], placements: [], teamId: Number(safeRead("aisana.team")) || null, role: safeRead("aisana.role") || "business", taskId: null, draftId: null, questions: [], view: "city", mode: "map"};
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c]));
  const num = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const activeTeam = () => state.teams.find((team) => team.id === state.teamId);
  const isBusiness = () => state.role === "business";
  const empty = (text) => `<div class="empty panel">${esc(text)}</div>`;
  const button = (label, action, attrs = "") => `<button type="button" class="btn secondary small" data-action="${action}" ${attrs}>${esc(label)}</button>`;
  function notice(message, error = false) { $("notice").hidden = false; $("notice").className = `notice${error ? " error" : ""}`; $("notice").textContent = message; if (error) $("notice").scrollIntoView({block: "center"}); }
  function errorText(detail) { if (Array.isArray(detail)) return detail.map((item) => `${(item.loc || []).slice(1).join(".")}: ${item.msg}`).join("; "); return typeof detail === "string" ? detail : "Не удалось выполнить запрос."; }
  async function api(path, method = "GET", body) {
    let response;
    try { response = await fetch(path, {method, headers: body === undefined ? {} : {"Content-Type": "application/json"}, ...(body === undefined ? {} : {body: JSON.stringify(body)})}); }
    catch (_) { throw new Error("Нет связи с backend. Убедитесь, что приложение запущено, и повторите действие."); }
    const text = await response.text(); let data;
    try { data = text ? JSON.parse(text) : null; } catch (_) { throw new Error(`Сервер вернул неожиданный ответ (${response.status}).`); }
    if (!response.ok) throw new Error(errorText(data?.detail)); return data;
  }
  async function run(control, work) {
    const controls = control ? [...(control.matches("button") ? [control] : control.querySelectorAll("button"))] : [];
    const disabled = controls.map((item) => item.disabled); controls.forEach((item) => { item.disabled = true; }); control?.setAttribute("aria-busy", "true");
    try { await work(); } catch (error) { notice(error.message, true); }
    finally { controls.forEach((item, index) => { item.disabled = disabled[index]; }); control?.removeAttribute("aria-busy"); }
  }
  function go(view) {
    state.view = view;
    document.querySelectorAll(".view").forEach((node) => node.classList.toggle("active", node.id === `view-${view}`));
    document.querySelectorAll(".tab-btn").forEach((node) => { node.setAttribute("aria-selected", String(node.dataset.view === view)); if (node.dataset.view === view) node.setAttribute("aria-current", "page"); else node.removeAttribute("aria-current"); });
    if (view === "create") run(null, loadDrafts); if (view === "missions") run(null, loadMission); if (view === "workshop") run(null, loadWorkshop); if (view === "final") run(null, loadBoss);
    window.scrollTo({top: 0, behavior: "instant"});
  }
  function ratingHtml(score) { const value = Math.min(100, Math.max(0, num(score))); return `<div class="readiness-row"><div class="readiness-bar" role="meter" aria-label="Готовность карточки" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${value}"><div class="readiness-fill" style="width:${value}%"></div></div><span class="readiness-num">${value} / 100</span></div>`; }
  function options(tasks, selected) { return `<option value="">Выберите задачу</option>` + tasks.map((task) => `<option value="${task.id}"${task.id === selected ? " selected" : ""}>${esc(task.title)}</option>`).join(""); }
  function syncTaskPickers() { ["missionTaskSelect", "bossTaskSelect", "collectionTaskSelect"].forEach((id) => { const value = Number($(id).value) || state.taskId; $(id).innerHTML = options(state.tasks, value); }); }
  async function loadTeams() {
    state.teams = await api("/api/teams"); if (!activeTeam()) state.teamId = state.teams[0]?.id || null;
    $("teamSelect").innerHTML = `<option value="">Выберите команду</option>` + state.teams.map((team) => `<option value="${team.id}">${esc(team.name)}</option>`).join("");
    $("teamSelect").value = state.teamId || ""; $("coinCount").textContent = activeTeam()?.coins ?? "—"; safeWrite("aisana.team", state.teamId || "");
  }
  async function loadCatalog() {
    $("taskCount").textContent = "Загружаем задачи…";
    let tasks, placements;
    try { [tasks, placements] = await Promise.all([api(`/api/tasks?sort=${$("sortFilter").value}`), api("/api/ui/placements?mode=top_down_houses")]); }
    catch (error) { $("taskCount").textContent = "Не удалось загрузить. Нажмите «Обновить»."; throw error; }
    state.tasks = tasks; state.placements = placements; const tag = $("tagFilter").value;
    $("tagFilter").innerHTML = `<option value="">Все категории</option>` + [...new Set(tasks.map((task) => task.tag))].sort().map((item) => `<option value="${esc(item)}">${esc(item)}</option>`).join(""); $("tagFilter").value = tag; syncTaskPickers(); renderCatalog();
  }
  function renderCatalog() {
    const search = $("searchInput").value.trim().toLocaleLowerCase("ru");
    const filtered = state.tasks.filter((task) => (!$("tagFilter").value || task.tag === $("tagFilter").value) && (!$("levelFilter").value || task.level === $("levelFilter").value) && (!search || `${task.title} ${task.context_need} ${task.tag}`.toLocaleLowerCase("ru").includes(search)));
    $("taskCount").textContent = `Задач: ${filtered.length}`; $("cityEmpty").hidden = filtered.length > 0;
    $("cityEmpty").textContent = state.tasks.length ? "По этим фильтрам задач нет. Измените условия поиска." : "Пока нет опубликованных задач. Создайте и подтвердите первую карточку.";
    $("cityMapMode").hidden = state.mode !== "map" || !filtered.length; $("cityListMode").hidden = state.mode !== "list" || !filtered.length;
    $("cityListMode").innerHTML = filtered.map((task) => `<button class="task-row linked" type="button" data-task="${task.id}"><span class="task-icon">🏠</span><span class="task-row-main"><span class="task-row-name">${esc(task.title)}</span><span class="task-row-quest">${esc(task.tag)} · ${esc(task.selected_team_name || "Открыта для предложений")}</span></span><span class="task-row-progress">${ratingHtml(task.score)}</span><span class="task-row-state">${esc(levels[task.level] || task.level)}</span></button>`).join(""); renderMap(filtered);
  }
  function renderMap(tasks) {
    const plots = tasks.map((task, index) => {
      const placement = state.placements.find((item) => item.task_id === task.id);
      return {task, placement, x: num(placement?.x, 100 + index % 5 * 170), y: num(placement?.y, 100 + Math.floor(index / 5) * 260), w: Math.max(40, num(placement?.width, 120)), h: Math.max(40, num(placement?.height, 110))};
    });
    const minX = Math.min(0, ...plots.map((plot) => plot.x - plot.w / 2 - 40));
    const minY = Math.min(0, ...plots.map((plot) => plot.y - plot.h * (.35 + Math.min(100, Math.max(0, num(plot.task.score))) * .0075) - plot.w / 4 - 50));
    const width = Math.max(950, ...plots.map((plot) => plot.x + plot.w / 2 + 40)) - minX;
    const height = Math.max(400, ...plots.map((plot) => plot.y + plot.w / 4 + 80)) - minY;
    $("isoSvg").setAttribute("viewBox", `${minX} ${minY} ${width} ${height}`); $("isoSvg").parentElement.style.aspectRatio = `${width}/${height}`;
    $("isoSvg").innerHTML = `<defs><pattern id="cityGrid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" opacity=".04"/></pattern></defs><rect x="${minX}" y="${minY}" width="${width}" height="${height}" fill="url(#cityGrid)"/>` + plots.sort((a,b) => a.y-b.y).map(({task, placement, x, y, w: sizeW, h: sizeH}) => {
      const score = Math.min(100, Math.max(0, num(task.score))), h = sizeH * (.35 + score * .0075), w = sizeW / 2, d = sizeW / 4;
      const windowCount = Math.max(1, Math.min(3, Math.floor(h / 24)));
      const windows = Array.from({length: windowCount}, (_, n) => `<rect x="${x+w*.5-4}" y="${y-h+d*.5+h*(n+.5)/windowCount-4}" width="8" height="8" class="${n < Math.ceil(score/100*windowCount) ? "win-lit-iso" : "win-dim-iso"}"/>`).join("");
      return `<g class="bld-group linked" data-task="${task.id}" role="button" tabindex="0" aria-label="${esc(task.title)}. Готовность ${score} из 100" data-asset="${esc(placement?.visual_asset_key || "house")}"><title>${esc(task.title)} — ${score}/100</title><polygon class="plot-fill" points="${x},${y-d} ${x+w+14},${y} ${x},${y+d+16} ${x-w-14},${y}"/><polygon class="bld-left" points="${x-w},${y-h} ${x},${y-h+d} ${x},${y+d} ${x-w},${y}"/><polygon class="bld-right" points="${x},${y-h+d} ${x+w},${y-h} ${x+w},${y} ${x},${y+d}"/><polygon class="bld-top${score >= 90 ? " featured" : ""}" points="${x},${y-h-d} ${x+w},${y-h} ${x},${y-h+d} ${x-w},${y-h}"/>${windows}<text x="${x}" y="${y-h-d-24}" text-anchor="middle" class="svg-title">${esc(task.title.length > 25 ? task.title.slice(0,24) + "…" : task.title)}</text><text x="${x}" y="${y+61}" text-anchor="middle" class="svg-caption">${score}/100 · ${esc(levels[task.level] || "Готовность")}</text></g>`;
    }).join("");
  }
  function missingRecommendations(items) {
    return `<div class="missing-recommendations"><h3>Как повысить готовность</h3>${items.length ? `<ul>${items.map((item) => `<li>Добавьте поле «${esc(item.label)}» — <strong>+${num(item.weight)} баллов</strong>.</li>`).join("")}</ul><p class="muted">Баллы начисляются после проверки и подтверждения сведений бизнесом.</p>` : '<p class="muted">Все семь полей заполнены. Проверьте сведения и подтвердите карточку.</p>'}</div>`;
  }
  function showAi(result) {
    $("aiStatus").textContent = result.ai_used ? "Подготовлено с помощью AI. Проверьте факты." : `Сейчас используется локальный шаблон; внешний AI не участвовал.${result.fallback_reason ? " " + result.fallback_reason : ""}`;
    if (Array.isArray(result.covered_fields) && Array.isArray(result.missing_fields)) {
      let summary = $("aiCoverage");
      if (!summary) { summary = document.createElement("div"); summary.id = "aiCoverage"; summary.className = "analysis-summary"; $("aiStatus").after(summary); }
      const labels = (keys) => keys.map((key) => fields.find(([field]) => field === key)?.[1] || key);
      const covered = labels(result.covered_fields), missing = labels(result.missing_fields);
      summary.innerHTML = `<div><h3>Уже есть в описании</h3><p>${covered.length ? covered.map(esc).join(", ") : "Пока нет достаточно конкретных сведений."}</p></div><div><h3>Нужно уточнить</h3><p>${missing.length ? missing.map(esc).join(", ") : "Основные поля упомянуты. Ответьте на вопросы, чтобы проверить детали."}</p></div><p class="muted">Это анализ исходного описания, а не подтверждение фактов и не начисленные баллы.</p>`;
      summary.hidden = false;
    }
  }
  function renderQuestions(questions) { state.questions = questions; if ($("aiCoverage")) $("aiCoverage").hidden = true; $("questionFields").innerHTML = questions.map((question, index) => `<label>${index+1}. ${esc(question.question)}<textarea data-question="${index}" rows="3" placeholder="Ваш ответ. Если данных нет, укажите это.">${esc(question.answer || "")}</textarea></label>`).join(""); $("questionsForm").hidden = !questions.length; }
  function renderCard(task) { $("cardTitle").value = task.title || $("draftTitle").value; $("cardFields").innerHTML = fields.map(([key, label]) => `<label>${label}<textarea name="${key}" rows="3">${esc(task.fields?.[key] ?? task[key] ?? "")}</textarea></label>`).join(""); $("cardForm").hidden = false; $("confirmCard").checked = false; previewRating(); }
  function readCardFields() { return Object.fromEntries(fields.map(([key]) => [key, $("cardFields").querySelector(`[name="${key}"]`).value.trim()])); }
  function previewRating() {
    const values = readCardFields();
    const score = fields.reduce((sum, [key, , weight]) => sum + (values[key] ? weight : 0), 0);
    const missing = fields.filter(([key]) => !values[key]).map(([key, label, weight]) => ({key, label, weight}));
    $("cardPreview").innerHTML = `<h3>Предварительный рейтинг после подтверждения</h3><p>Это прогноз по заполненным полям. Итоговый рейтинг рассчитывается после проверки и подтверждения карточки.</p>${ratingHtml(score)}${missingRecommendations(missing)}`;
  }
  async function saveDraft() {
    if (!$("draftForm").reportValidity()) return null;
    const payload = {title: $("draftTitle").value.trim(), tag: $("draftTag").value.trim(), draft_text: $("draftText").value.trim()};
    const task = await api(state.draftId ? `/api/tasks/${state.draftId}` : "/api/tasks", state.draftId ? "PATCH" : "POST", payload);
    state.draftId = task.id; $("draftStatus").textContent = `Черновик №${task.id} сохранён`; await loadDrafts(); return task;
  }
  async function loadDrafts() { state.drafts = await api("/api/tasks?status=draft&sort=new"); $("draftList").innerHTML = state.drafts.length ? state.drafts.map((task) => `<button type="button" class="draft-item" data-draft="${task.id}">${esc(task.title)}<span>Продолжить →</span></button>`).join("") : `<p class="muted">Пока нет черновиков.</p>`; }
  function newDraft() { state.draftId = null; state.questions = []; $("draftForm").reset(); $("questionsForm").hidden = true; $("cardForm").hidden = true; $("draftStatus").textContent = "Черновик ещё не сохранён"; }
  async function openDraft(id) {
    const [task, questions] = await Promise.all([api(`/api/tasks/${id}`), api(`/api/tasks/${id}/questions`)]);
    state.draftId = task.id; $("draftTitle").value = task.title; $("draftTag").value = task.tag; $("draftText").value = task.draft_text || task.context_need || "";
    $("draftStatus").textContent = `Загружена карточка №${task.id}. Изменения сохраняются как черновик.`;
    renderQuestions(questions); $("aiStatus").textContent = "Сохранённые вопросы и ответы. Проверьте актуальность перед сборкой карточки."; renderCard(task); go("create");
  }
  async function saveCard() { if (!state.draftId) throw new Error("Сначала сохраните исходное описание."); return api(`/api/tasks/${state.draftId}`, "PATCH", {title: $("cardTitle").value.trim(), tag: $("draftTag").value.trim(), fields: readCardFields()}); }
  async function openTask(id) {
    state.taskId = Number(id); syncTaskPickers(); go("task"); $("taskDetail").innerHTML = empty("Загружаем карточку…");
    const [task, rating, responses] = await Promise.all([api(`/api/tasks/${id}`), api(`/api/tasks/${id}/rating`), api(`/api/tasks/${id}/responses`)]);
    $("taskDetail").innerHTML = `<div class="button-row">${button("← В город", "city")}${isBusiness() ? button("Редактировать карточку", "edit-task", `data-id="${id}"`) : ""}${button("Открыть миссию", "mission", `data-id="${id}"`)}</div><div class="view-head"><div class="eyebrow">${esc(task.tag)} · ${esc(levels[task.level] || task.level)}</div><h1>${esc(task.title)}</h1><p class="desc">${task.selected_team_name ? "Выбрана команда: " + esc(task.selected_team_name) : "Бизнес рассматривает предложения команд"}</p></div><div class="mission-grid"><div class="side-stack"><div class="panel task-fields">${fields.map(([key, label]) => `<div><h3>${label}</h3><p class="prewrap">${esc(task[key] || "Пока не указано")}</p></div>`).join("")}</div><div class="panel"><h2>Предложения команд</h2><div class="response-list">${responses.length ? responses.map(responseHtml).join("") : `<p class="muted">Предложений пока нет.</p>`}</div></div></div><aside class="side-stack"><div class="panel"><h3>Готовность карточки</h3>${ratingHtml(rating.score)}<p class="muted">Это полнота описания, а не оценка команды или результата.</p><div class="breakdown">${rating.breakdown.map((item) => `<div><span>${item.confirmed ? "✓" : "○"} ${esc(item.label)}</span><span>${item.awarded_points ?? (item.confirmed && item.filled ? item.weight : 0)}/${item.weight}</span></div>`).join("")}</div></div><form id="responseForm" class="panel form-stack"><h2>Предложить решение</h2><p class="muted">${activeTeam() ? "От команды «" + esc(activeTeam().name) + "»" : "Создайте команду в мастерской и выберите её сверху."}</p><label>Идея<textarea name="idea" rows="3" required></textarea></label><label>План<textarea name="plan" rows="3" required></textarea></label><label>Срок в днях<input name="deadline_days" type="number" min="1" max="3650" required></label><label>Ссылка на прототип (необязательно)<input name="prototype_link" type="url" placeholder="https://…"></label><button class="btn primary" type="submit" ${!activeTeam() || isBusiness() ? "disabled" : ""}>Отправить предложение</button>${isBusiness() ? '<p class="muted">Чтобы отправить предложение, переключите демо-роль на «Команда».</p>' : ""}</form></aside></div>`;
    const missing = rating.breakdown.filter((item) => (rating.missing_fields || []).includes(item.key) || (rating.missing_fields || []).includes(item.label));
    $("taskDetail").querySelector(".breakdown").insertAdjacentHTML("afterend", missingRecommendations(missing));
    $("responseForm").addEventListener("submit", (event) => { event.preventDefault(); const form = event.currentTarget; run(form, async () => { const data = Object.fromEntries(new FormData(form)); data.team_id = state.teamId; data.team_name = activeTeam()?.name; data.deadline_days = Number(data.deadline_days); await api(`/api/tasks/${id}/responses`, "POST", data); notice("Предложение отправлено бизнесу."); await openTask(id); }); });
  }
  function responseHtml(response) {
    const link = /^https?:\/\//i.test(response.prototype_link || "") ? `<a href="${esc(response.prototype_link)}" target="_blank" rel="noopener noreferrer">Открыть прототип ↗</a>` : "";
    return `<article class="response-card"><div class="section-heading"><h3>${esc(response.team_name)}</h3><span class="badge">${esc(statuses[response.status] || response.status)}</span></div><p class="prewrap">${esc(response.idea)}</p><p class="muted prewrap">${esc(response.plan)}</p><p class="muted">Срок: ${response.deadline_days ? `${response.deadline_days} дн.` : "не указан"}</p>${link}${isBusiness() && response.status === "pending" ? `<div class="button-row">${button("Выбрать команду", "select-response", `data-id="${response.id}"`)}${button("Отклонить", "reject-response", `data-id="${response.id}"`)}</div>` : ""}</article>`;
  }
  async function loadMission() {
    const id = Number($("missionTaskSelect").value) || state.taskId; if (!id) { $("missionContent").innerHTML = empty("Выберите задачу. Миссия начинается после ручного выбора команды бизнесом."); return; }
    $("missionTaskSelect").value = id;
    const [task, steps, selectedTeams] = await Promise.all([api(`/api/tasks/${id}`), api(`/api/tasks/${id}/quests`), api(`/api/tasks/${id}/selected-teams`)]);
    const canWork = !isBusiness() && selectedTeams.some((team) => team.id === state.teamId);
    $("missionContent").innerHTML = `<div class="mission-grid"><div class="panel mission-story"><h2>${esc(task.title)}</h2><p class="muted">${selectedTeams.length ? "Выбраны: " + selectedTeams.map((team) => esc(team.name)).join(", ") : "Команда ещё не выбрана бизнесом"}</p>${!isBusiness() && !canWork ? '<p class="ai-status">Для работы над этапами бизнес должен выбрать предложение вашей команды.</p>' : ""}<div class="quest-path">${steps.length ? steps.map((step) => `<article class="quest-step ${step.status === "done" ? "done" : step.status === "locked" ? "locked" : "current"}"><span class="node"></span><h3 class="qtitle">${step.step_order}. ${esc(step.title)}</h3><span class="qstatus review">${esc(stepLabels[step.status])}</span>${step.submission_text ? `<p class="prewrap result-text">${esc(step.submission_text)}</p>` : ""}${step.path_choice ? `<p class="muted">Выбранный путь: ${esc(step.path_choice)}</p>` : ""}${step.status === "current" ? `<label class="path-choice">Как проверим идею?<select data-path-step="${step.id}" data-task-id="${id}" ${!canWork ? "disabled" : ""}><option value="">Выберите подход</option>${["Интервью с пользователями", "Прототип и тестирование", "Анализ данных"].map((choice) => `<option ${step.path_choice === choice ? "selected" : ""}>${choice}</option>`).join("")}</select></label><div class="hint-box">${button(step.hint_level >= 3 ? "Все подсказки раскрыты" : "Показать подсказку", "hint", `data-step="${step.id}" data-task-id="${id}" ${step.hint_level >= 3 || !canWork ? "disabled" : ""}`)}<div class="hint-levels" id="hints-${step.id}">${(step.hints || []).map((hint) => `<p>${esc(hint)}</p>`).join("")}</div></div>${canWork ? `<form class="step-form form-stack" data-step="${step.id}" data-task-id="${id}"><label>Результат этапа<textarea name="submission_text" rows="3" required placeholder="Что сделано, где посмотреть результат, что проверили"></textarea></label><button class="btn primary small" type="submit">Отправить на проверку</button></form>` : ""}` : ""}${step.status === "review" && isBusiness() ? `<div class="button-row">${button("Подтвердить этап", "confirm-step", `data-step="${step.id}" data-task-id="${id}"`)}</div>` : ""}</article>`).join("") : `<p class="muted">Этапов пока нет. Сначала бизнес должен выбрать предложение команды.</p>`}</div></div><aside class="panel"><h3>Готовность карточки</h3>${ratingHtml(task.score)}<p class="muted">Прогресс миссии: ${steps.filter((step) => step.status === "done").length} из ${steps.length} этапов подтверждено.</p><div class="button-row">${button("Открыть карточку", "task", `data-id="${id}"`)}${button("Финальная проверка", "boss", `data-id="${id}"`)}</div></aside></div>`;
    $("missionContent").querySelectorAll(".step-form").forEach((form) => form.addEventListener("submit", (event) => { event.preventDefault(); run(form, async () => { await api(`/api/tasks/${id}/quests/${form.dataset.step}/submit`, "POST", {submission_text: new FormData(form).get("submission_text"), team_id: state.teamId}); notice("Результат отправлен бизнесу на проверку."); await loadMission(); }); }));
  }
  async function loadWorkshop() {
    const team = activeTeam();
    if (!team) { $("teamCard").innerHTML = `<h2>Соберите команду</h2><p class="muted">Создайте команду ниже или выберите существующую сверху.</p>`; $("shopItems").innerHTML = ""; $("collectionItems").innerHTML = ""; return; }
    Object.assign(team, await api(`/api/teams/${team.id}`)); $("coinCount").textContent = team.coins;
    $("teamCard").innerHTML = `<div class="team-head"><div class="team-avatar">${esc(team.avatar_emoji)}</div><div><h2>${esc(team.name)}</h2><p class="team-sub">${team.experience} опыта · ${team.coins} монет</p></div></div><div class="task-fields"><div><h3>Навыки</h3><p>${esc(team.skills || "Пока не указаны")}</p></div><div><h3>Технологии</h3><p>${esc(team.technologies || "Пока не указаны")}</p></div><div><h3>Интересы</h3><p>${esc(team.interests || "Пока не указаны")}</p></div></div><div class="member-list">${team.members.map((member) => `<div class="member-row"><span>${esc(member.name)}</span><span class="member-title">${esc(member.title || "Участник")}</span></div>`).join("")}</div>`;
    const items = await api(`/api/teams/${team.id}/shop-items`);
    $("shopItems").innerHTML = items.length ? items.map(({item, owned, equipped}) => `<div class="shop-item${equipped ? " equipped" : ""}"><span class="icon">${esc(item.icon)}</span><h3>${esc(item.name)}</h3><span class="cost">${item.cost} 🪙</span>${equipped ? '<span class="equipped-tag">Выбрано</span>' : button(owned ? "Выбрать" : "Открыть", owned ? "equip" : "purchase", `data-id="${item.id}" ${!owned && team.coins < item.cost ? "disabled" : ""}`)}</div>`).join("") : `<p class="muted">В магазине пока нет предметов.</p>`;
    await loadCollection();
  }
  async function loadCollection() { const id = Number($("collectionTaskSelect").value) || state.taskId; if (!state.teamId || !id) { $("collectionItems").innerHTML = `<p class="muted">Выберите команду и задачу.</p>`; return; } $("collectionTaskSelect").value = id; const pieces = await api(`/api/teams/${state.teamId}/collection/${id}`); $("collectionItems").innerHTML = pieces.map((piece) => `<div class="collection-piece ${piece.unlocked ? "got" : "locked"}"><span class="piece-icon">${piece.unlocked ? "✓" : "◇"}</span>${esc(collectionLabels[piece.type] || piece.type)}</div>`).join(""); }
  async function loadBoss() {
    const id = Number($("bossTaskSelect").value) || state.taskId; if (!id) { $("bossContent").innerHTML = empty("Выберите задачу для финальной проверки."); return; } $("bossTaskSelect").value = id;
    const [task, status, steps] = await Promise.all([api(`/api/tasks/${id}`), api(`/api/tasks/${id}/boss-criteria`), api(`/api/tasks/${id}/quests`)]);
    const ready = steps.length > 0 && steps.every((step) => step.status === "done");
    $("bossContent").innerHTML = `<div class="panel boss-panel"><h2>${esc(task.title)}</h2><p class="muted">${!ready ? "Сначала завершите и подтвердите все этапы миссии." : isBusiness() ? "Подтверждайте критерии после проверки результата команды." : "Критерии подтверждает бизнес. Переключение демо-роли доступно сверху."}</p><div class="boss-bar-wrap"><div class="boss-bar-label"><span>Проблема под контролем</span><span>${status.confirmed_count} / ${status.total} подтверждено</span></div><div class="boss-bar">${status.criteria.map((item) => `<div class="boss-seg${item.confirmed ? " confirmed" : ""}"></div>`).join("")}</div></div><div class="criteria-list">${status.criteria.length ? status.criteria.map((item) => `<button type="button" class="criterion${item.confirmed ? " confirmed" : ""}" data-action="boss-confirm" data-id="${item.id}" data-task-id="${id}" ${!isBusiness() || item.confirmed || !ready ? "disabled" : ""}><span class="crit-box">${item.confirmed ? "✓" : ""}</span><span class="crit-text">${esc(item.text)}</span></button>`).join("") : `<p class="muted">Критерии появятся из опубликованной карточки задачи.</p>`}</div>${status.completed ? '<div class="celebration show">Все критерии подтверждены. Решение принято, награда сохранена для команды.</div>' : ""}</div>`;
  }
  // Delegated handlers cover content refreshed after successful API writes.
  document.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-view]"); if (tab) { go(tab.dataset.view); return; }
    const mode = event.target.closest("[data-mode]"); if (mode) { state.mode = mode.dataset.mode; document.querySelectorAll("[data-mode]").forEach((node) => { node.classList.toggle("active", node === mode); node.setAttribute("aria-pressed", String(node === mode)); }); renderCatalog(); return; }
    const task = event.target.closest("[data-task]"); if (task) { run(null, () => openTask(Number(task.dataset.task))); return; }
    const draft = event.target.closest("[data-draft]"); if (draft) { run(draft, () => openDraft(Number(draft.dataset.draft))); return; }
    const control = event.target.closest("[data-action]"); if (!control || control.disabled) return;
    run(control, async () => {
      const action = control.dataset.action, id = Number(control.dataset.id), taskId = Number(control.dataset.taskId), step = Number(control.dataset.step);
      if (action === "city") go("city");
      else if (action === "task") await openTask(id);
      else if (action === "edit-task") await openDraft(id);
      else if (action === "mission" || action === "boss") { state.taskId = id; syncTaskPickers(); $(action === "mission" ? "missionTaskSelect" : "bossTaskSelect").value = id; go(action === "mission" ? "missions" : "final"); }
      else if (action === "select-response" || action === "reject-response") { await api(`/api/responses/${id}/${action === "select-response" ? "select" : "reject"}`, "PATCH"); notice(action === "select-response" ? "Команда выбрана бизнесом. Можно начать миссию." : "Предложение отклонено."); await loadCatalog(); await openTask(state.taskId); }
      else if (action === "hint") { const result = await api(`/api/tasks/${taskId}/quests/${step}/hint`, "POST"); if (result.hint) { const p = document.createElement("p"); p.textContent = result.hint; $(`hints-${step}`).append(p); } control.textContent = result.exhausted ? "Все подсказки раскрыты" : "Следующая подсказка"; if (result.exhausted) control.dataset.exhausted = "true"; }
      else if (action === "confirm-step") { await api(`/api/tasks/${taskId}/quests/${step}/confirm`, "POST"); notice("Этап подтверждён. Награда начислена."); await loadTeams(); await loadMission(); }
      else if (action === "purchase" || action === "equip") { await api(`/api/teams/${state.teamId}/shop-items/${id}/${action}`, "POST"); notice(action === "purchase" ? "Предмет добавлен в мастерскую." : "Оформление выбрано."); await loadWorkshop(); }
      else if (action === "boss-confirm") { await api(`/api/tasks/${taskId}/boss-criteria/${id}/toggle`, "PATCH"); notice("Проверка подтверждена."); await loadTeams(); await loadBoss(); }
    }).then(() => { if (control.dataset.exhausted) control.disabled = true; });
  });
  document.addEventListener("keydown", (event) => { const item = event.target.closest("g[data-task]"); if (item && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); item.dispatchEvent(new MouseEvent("click", {bubbles: true})); } });
  document.addEventListener("change", (event) => { const control = event.target.closest("[data-path-step]"); if (control && control.value) run(control, async () => { await api(`/api/tasks/${control.dataset.taskId}/quests/${control.dataset.pathStep}/path-choice`, "PATCH", {choice: control.value}); notice("Путь прохождения сохранён."); }); });
  $("roleSelect").value = state.role;
  $("roleSelect").addEventListener("change", () => { state.role = $("roleSelect").value; safeWrite("aisana.role", state.role); if (state.view === "task") run(null, () => openTask(state.taskId)); else go(state.view); });
  $("teamSelect").addEventListener("change", () => { state.teamId = Number($("teamSelect").value) || null; safeWrite("aisana.team", state.teamId || ""); $("coinCount").textContent = activeTeam()?.coins ?? "—"; if (state.view === "task") run(null, () => openTask(state.taskId)); else if (state.view === "workshop") run(null, loadWorkshop); else if (state.view === "missions") run(null, loadMission); });
  $("filterForm").addEventListener("submit", (event) => { event.preventDefault(); run(event.currentTarget, loadCatalog); });
  ["searchInput", "tagFilter", "levelFilter"].forEach((id) => $(id).addEventListener(id === "searchInput" ? "input" : "change", renderCatalog));
  $("sortFilter").addEventListener("change", () => run(null, loadCatalog));
  $("newDraftBtn").addEventListener("click", newDraft);
  $("saveDraftBtn").addEventListener("click", (event) => run(event.currentTarget, async () => { if (await saveDraft()) notice("Черновик сохранён."); }));
  $("draftForm").addEventListener("submit", (event) => { event.preventDefault(); run(event.currentTarget, async () => { const task = await saveDraft(); if (!task) return; const result = await api("/api/ai/analyze", "POST", {task_id: task.id, draft_text: $("draftText").value.trim()}); state.draftId = result.task_id || task.id; renderQuestions(result.questions); showAi(result); $("cardForm").hidden = true; notice("Описание сохранено. Ответьте на уточняющие вопросы."); }); });
  $("questionsForm").addEventListener("submit", (event) => { event.preventDefault(); run(event.currentTarget, async () => { const answers = state.questions.map((question, index) => ({field: question.field, question: question.question, answer: $("questionFields").querySelector(`[data-question="${index}"]`).value.trim()})); const result = await api("/api/ai/assemble", "POST", {task_id: state.draftId, draft_text: $("draftText").value.trim(), answers}); renderCard(result); showAi(result); await loadDrafts(); notice("Карточка собрана и сохранена как черновик. Проверьте её перед публикацией."); }); });
  $("cardFields").addEventListener("input", () => { $("confirmCard").checked = false; previewRating(); });
  $("cardTitle").addEventListener("input", () => { $("confirmCard").checked = false; });
  $("saveCardBtn").addEventListener("click", (event) => run(event.currentTarget, async () => { if (!$("cardTitle").reportValidity()) return; await saveCard(); await loadDrafts(); await loadCatalog(); notice("Карточка сохранена без публикации."); }));
  $("cardForm").addEventListener("submit", (event) => { event.preventDefault(); run(event.currentTarget, async () => { if (!$("confirmCard").checked) throw new Error("Подтвердите достоверность карточки."); await saveCard(); const task = await api(`/api/tasks/${state.draftId}/publish`, "POST", {confirmed: true}); await loadCatalog(); await loadDrafts(); newDraft(); notice("Карточка подтверждена и опубликована в городе."); await openTask(task.id); }); });
  $("teamForm").addEventListener("submit", (event) => { event.preventDefault(); const form = event.currentTarget; run(form, async () => { const values = Object.fromEntries(new FormData(form)); values.members = values.members.split(/\r?\n/).map((name) => name.trim()).filter(Boolean).map((name) => ({name})); const team = await api("/api/teams", "POST", values); state.teamId = team.id; await loadTeams(); form.reset(); await loadWorkshop(); notice("Команда создана и выбрана."); }); });
  $("missionTaskSelect").addEventListener("change", () => { state.taskId = Number($("missionTaskSelect").value) || null; run(null, loadMission); });
  $("bossTaskSelect").addEventListener("change", () => { state.taskId = Number($("bossTaskSelect").value) || null; run(null, loadBoss); });
  $("collectionTaskSelect").addEventListener("change", () => run(null, loadCollection));
  $("brand").addEventListener("click", (event) => { event.preventDefault(); go("city"); });
  run(null, async () => { await Promise.all([loadTeams(), loadCatalog()]); if (location.hash === "#create") go("create"); });
})();
