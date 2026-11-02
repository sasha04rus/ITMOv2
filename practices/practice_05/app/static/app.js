"use strict";

(() => {
  const form = document.getElementById("search-form");
  const input = document.getElementById("search-input");
  const resetButton = document.getElementById("reset-button");
  const retryButton = document.getElementById("retry-button");
  const directory = document.getElementById("directory");
  const results = document.getElementById("results");
  const status = document.getElementById("status");
  const count = document.getElementById("result-count");
  const appliedQuery = document.getElementById("applied-query");
  const fallbackMessage = "Не удалось загрузить подписчиков. Попробуйте ещё раз";

  let lastSubmittedQuery = "";
  let newestRequest = 0;
  let activeController = null;

  const isObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);

  function isSearchResponse(data) {
    return isObject(data)
      && typeof data.query === "string"
      && Array.isArray(data.items)
      && data.items.every((item) => typeof item === "string")
      && Number.isSafeInteger(data.total)
      && data.total >= 0
      && data.total === data.items.length;
  }

  function isErrorResponse(data) {
    return isObject(data)
      && isObject(data.error)
      && typeof data.error.code === "string"
      && data.error.code.length > 0
      && typeof data.error.message === "string"
      && data.error.message.length > 0;
  }

  function setState(state, message) {
    directory.dataset.state = state;
    status.dataset.state = state;
    status.textContent = message;
    retryButton.hidden = state !== "error";
    results.hidden = state !== "success";
    count.hidden = state !== "success" && state !== "empty";
    appliedQuery.hidden = true;
    appliedQuery.textContent = "";
    results.replaceChildren();
    count.textContent = "";
    results.setAttribute("aria-busy", String(state === "loading"));
  }

  function showResponse(data) {
    const state = data.total === 0 ? "empty" : "success";
    setState(state, state === "empty" ? "Ничего не найдено" : "Список обновлён");
    count.textContent = `Найдено: ${data.total}`;

    if (data.query !== "") {
      appliedQuery.textContent = `По запросу «${data.query}»`;
      appliedQuery.hidden = false;
    }

    const fragment = document.createDocumentFragment();
    for (const name of data.items) {
      const row = document.createElement("li");
      row.className = "subscriber";
      row.dataset.name = name;

      const avatar = document.createElement("span");
      avatar.className = "subscriber-avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = Array.from(name)[0]?.toLocaleUpperCase("ru") || "·";

      const label = document.createElement("span");
      label.className = "subscriber-name";
      label.textContent = name;

      row.append(avatar, label);
      fragment.append(row);
    }
    results.append(fragment);
  }

  async function search(rawQuery) {
    const requestId = ++newestRequest;
    lastSubmittedQuery = rawQuery;
    activeController?.abort();
    const controller = new AbortController();
    activeController = controller;
    setState("loading", "Загрузка…");

    const url = new URL("/api/subscribers", window.location.origin);
    if (rawQuery !== "") {
      url.searchParams.set("q", rawQuery);
    }

    try {
      const response = await fetch(url.pathname + url.search, {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
        signal: controller.signal,
      });
      if (requestId !== newestRequest) return;

      const data = await response.json();
      if (requestId !== newestRequest) return;

      if (response.status === 200 && isSearchResponse(data)) {
        showResponse(data);
      } else if (response.status === 400 && isErrorResponse(data)) {
        setState("error", data.error.message);
      } else {
        setState("error", fallbackMessage);
      }
    } catch (error) {
      if (requestId !== newestRequest) return;
      if (error?.name === "AbortError" && controller.signal.aborted) return;
      setState("error", fallbackMessage);
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    void search(input.value);
  });

  resetButton.addEventListener("click", () => {
    input.value = "";
    input.focus();
    void search("");
  });

  retryButton.addEventListener("click", () => {
    void search(lastSubmittedQuery);
  });

  void search("");
})();
