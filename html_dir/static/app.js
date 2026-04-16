const state = {
  content: null,
  me: null,
  answered: new Set(),
  quizIndex: 0,
  wikiImageCache: new Map(),
};

async function initSessionFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const userId = params.get("user_id");
  const username = params.get("username");

  if (!userId || !username) {
    return;
  }

  await fetch("/api/session/init", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, username }),
  });
}

async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    throw new Error(`${url} -> ${res.status}`);
  }
  return res.json();
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = value;
  }
}

function renderProjectInfo() {
  const project = state.content.project;
  setText("project-title", project.title);
  setText("project-goal", project.goal);
  setText("project-meta", `Тема: ${project.theme} | Команда: ${project.team.join(", ")}`);
  setText("project-note", project.note || "");
}

function renderTimeline() {
  const container = document.getElementById("timeline");
  container.innerHTML = "";

  state.content.timeline.forEach((item) => {
    const div = document.createElement("article");
    div.className = "timeline-item";
    div.innerHTML = `
      <h3>${item.label}</h3>
      <p><strong>${item.period}</strong></p>
      <p>${item.focus}</p>
    `;
    container.appendChild(div);
  });
}

async function getWikiThumbnailUrl(title) {
  if (!title) {
    return null;
  }
  if (state.wikiImageCache.has(title)) {
    return state.wikiImageCache.get(title);
  }

  try {
    const endpoint = `https://ru.wikipedia.org/w/api.php?action=query&prop=pageimages&titles=${encodeURIComponent(
      title
    )}&pithumbsize=900&format=json&origin=*`;
    const res = await fetch(endpoint);
    const data = await res.json();
    const pages = data?.query?.pages || {};
    const firstPage = Object.values(pages)[0];
    const image = firstPage?.thumbnail?.source || null;
    state.wikiImageCache.set(title, image);
    return image;
  } catch (error) {
    state.wikiImageCache.set(title, null);
    return null;
  }
}

function createObjectMarkup(obj) {
  const sourceLinks = obj.sources
    .map((sid) => {
      const source = state.content.sources[sid];
      if (!source) return "";
      return `<a href="${source.url}" target="_blank" rel="noopener">источник</a>`;
    })
    .filter(Boolean)
    .join(", ");

  return `
    <div class="object-card">
      <div class="object-photo placeholder" data-wiki-title="${obj.wiki_title || ""}">
        Фото загружается
      </div>
      <div class="object-content">
        <p><strong>${obj.name}</strong> (${obj.years})</p>
        <p>Архитекторы/авторы: ${obj.architects}.</p>
        <p>Заказчик: ${obj.customers}. Статус: ${obj.status}.</p>
        <p>Факт: ${obj.fact}</p>
        ${sourceLinks ? `<p>${sourceLinks}</p>` : ""}
      </div>
    </div>
  `;
}

async function hydrateRouteImages(container) {
  const placeholders = container.querySelectorAll(".object-photo.placeholder");
  await Promise.all(
    Array.from(placeholders).map(async (node) => {
      const title = node.getAttribute("data-wiki-title");
      if (!title) {
        node.textContent = "Фото не задано";
        return;
      }
      const imageUrl = await getWikiThumbnailUrl(title);
      if (!imageUrl) {
        node.textContent = "Фото недоступно";
        return;
      }
      const img = document.createElement("img");
      img.className = "object-photo";
      img.src = imageUrl;
      img.alt = title;
      node.replaceWith(img);
    })
  );
}

async function renderRoute() {
  const container = document.getElementById("route");
  container.innerHTML = "";

  state.content.route_stops.forEach((stop) => {
    const article = document.createElement("article");
    article.className = "route-stop";

    const objects = stop.objects.map((obj) => `<li>${createObjectMarkup(obj)}</li>`).join("");

    article.innerHTML = `
      <h3>${stop.title}</h3>
      <p class="period">${stop.period}</p>
      <p class="key-message">${stop.key_message}</p>
      <ul>${objects}</ul>
    `;

    container.appendChild(article);
  });

  await hydrateRouteImages(container);
}

function renderInfluences() {
  const container = document.getElementById("influences");
  container.innerHTML = "";

  state.content.european_influences.forEach((item) => {
    const li = document.createElement("li");
    const sourceLinks = item.sources
      .map((sid) => {
        const source = state.content.sources[sid];
        if (!source) return "";
        return `<a href="${source.url}" target="_blank" rel="noopener">${source.title}</a>`;
      })
      .filter(Boolean)
      .join("; ");

    li.innerHTML = `${item.thesis}${sourceLinks ? `<br/>${sourceLinks}` : ""}`;
    container.appendChild(li);
  });
}

function renderUnrealized() {
  const container = document.getElementById("unrealized");
  container.innerHTML = "";

  state.content.unrealized_projects.forEach((item) => {
    const sourceLinks = item.sources
      .map((sid) => {
        const source = state.content.sources[sid];
        if (!source) return "";
        return `<a href="${source.url}" target="_blank" rel="noopener">${source.title}</a>`;
      })
      .filter(Boolean)
      .join("; ");

    const div = document.createElement("article");
    div.className = "card";
    div.innerHTML = `
      <h3>${item.name}</h3>
      <p><strong>${item.period}</strong></p>
      <p>${item.why_important}</p>
      <p>${sourceLinks}</p>
    `;

    container.appendChild(div);
  });
}

function renderSources() {
  const container = document.getElementById("sources");
  container.innerHTML = "";

  Object.values(state.content.sources).forEach((source) => {
    const li = document.createElement("li");
    li.innerHTML = `<a href="${source.url}" target="_blank" rel="noopener">${source.title}</a>`;
    container.appendChild(li);
  });
}

function renderUser() {
  if (!state.me || !state.me.authorized) {
    setText("user-name", "Гость");
    setText("user-score", "0");
    setText("user-rank", "-");
    setText("user-answered", "0");

    document.getElementById("download-md").setAttribute("aria-disabled", "true");
    document.getElementById("download-md").classList.add("btn-secondary");
    return;
  }

  const user = state.me.user;
  setText("user-name", user.username);
  setText("user-score", String(user.score));
  setText("user-rank", state.me.rank ? String(state.me.rank) : "-");
  setText("user-answered", String(user.answered_total));

  const download = document.getElementById("download-md");
  download.removeAttribute("aria-disabled");
  download.classList.remove("btn-secondary");
}

function renderLeaderboard() {
  const container = document.getElementById("leaderboard");
  container.innerHTML = "";

  if (!state.me || !state.me.leaderboard.length) {
    container.innerHTML = "<p>Пока нет данных по рейтингу. Ответьте на квиз в Telegram-режиме.</p>";
    return;
  }

  state.me.leaderboard.forEach((item, index) => {
    const row = document.createElement("div");
    row.className = "leaderboard-row";
    const marker = state.me.user && item.id === state.me.user.id ? "<strong>Вы</strong>" : "";
    row.innerHTML = `
      <div>${index + 1}</div>
      <div>${item.username} ${marker}</div>
      <div>${item.score} б.</div>
    `;
    container.appendChild(row);
  });
}

function updateQuizProgress() {
  const total = state.content.quiz.length;
  const answered = state.answered.size;
  const currentLabel = Math.min(state.quizIndex + 1, total);

  setText("quiz-progress", `Вопрос ${currentLabel} из ${total} | Отвечено: ${answered}`);
  document.getElementById("quiz-progress-fill").style.width = `${(answered / total) * 100}%`;
}

function findNextUnanswered(startIndex = 0) {
  const questions = state.content.quiz;
  for (let i = startIndex; i < questions.length; i += 1) {
    if (!state.answered.has(questions[i].id)) {
      return i;
    }
  }
  return -1;
}

function renderQuizComplete() {
  const quizBox = document.getElementById("quiz-box");
  quizBox.innerHTML = `
    <h3>Квиз завершен</h3>
    <p>Вы прошли все вопросы. Экспортируйте отчёт и используйте его как основу для PDF/PPT защиты.</p>
  `;
}

function renderQuizQuestion() {
  const questions = state.content.quiz;
  const idx = findNextUnanswered(state.quizIndex);

  if (idx === -1) {
    renderQuizComplete();
    updateQuizProgress();
    return;
  }

  state.quizIndex = idx;
  const question = questions[idx];
  const quizBox = document.getElementById("quiz-box");
  const feedback = document.getElementById("quiz-feedback");
  feedback.innerHTML = "";

  const optionsHtml = question.options
    .map((option) => `<button class="option-btn" data-option="${option}">${option}</button>`)
    .join("");

  quizBox.innerHTML = `
    <p><strong>${question.question}</strong></p>
    <div class="option-grid">${optionsHtml}</div>
  `;

  quizBox.querySelectorAll(".option-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!state.me || !state.me.authorized) {
        feedback.className = "quiz-feedback feedback-bad";
        feedback.textContent = "Для сохранения прогресса откройте приложение через Telegram (/start).";
        return;
      }

      quizBox.querySelectorAll(".option-btn").forEach((item) => {
        item.disabled = true;
      });

      try {
        const payload = {
          question_id: question.id,
          selected_option: btn.dataset.option,
        };

        const result = await fetchJSON("/api/quiz/answer", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        state.answered.add(question.id);
        const sourceLinks = (result.sources || [])
          .map((s) => `<a href="${s.url}" target="_blank" rel="noopener">${s.title}</a>`)
          .join("; ");

        feedback.className = `quiz-feedback ${result.is_correct ? "feedback-ok" : "feedback-bad"}`;
        feedback.innerHTML = `
          ${result.is_correct ? "Верно." : "Есть ошибка."}
          ${result.explanation}
          ${sourceLinks ? `<br/>${sourceLinks}` : ""}
        `;

        state.me = await fetchJSON("/api/me");
        renderUser();
        renderLeaderboard();
        updateQuizProgress();

        const nextButton = document.createElement("button");
        nextButton.className = "btn";
        nextButton.style.marginTop = "10px";
        nextButton.textContent = "Следующий вопрос";
        nextButton.addEventListener("click", renderQuizQuestion);
        feedback.appendChild(document.createElement("br"));
        feedback.appendChild(nextButton);
      } catch (err) {
        feedback.className = "quiz-feedback feedback-bad";
        feedback.textContent = `Ошибка отправки ответа: ${err.message}`;
      }
    });
  });

  updateQuizProgress();
}

async function bootstrap() {
  await initSessionFromQuery();

  const [content, me] = await Promise.all([
    fetchJSON("/api/content"),
    fetchJSON("/api/me"),
  ]);

  state.content = content;
  state.me = me;
  state.answered = new Set(me.answered_question_ids || []);

  renderProjectInfo();
  renderTimeline();
  await renderRoute();
  renderInfluences();
  renderUnrealized();
  renderSources();
  renderUser();
  renderLeaderboard();
  renderQuizQuestion();
}

bootstrap().catch((err) => {
  console.error(err);
  const body = document.body;
  body.innerHTML = `<main class="layout"><section class="panel"><h2>Ошибка запуска</h2><p>${err.message}</p></section></main>`;
});
