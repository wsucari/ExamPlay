"use strict";

const ExamPlayLive = (() => {
  let reloadScheduled = false;

  function connect(gameId, role) {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${window.location.host}/ws/partidas/${gameId}/${role}/`;
    const socket = new WebSocket(url);
    socket.addEventListener("message", (message) => {
      const data = JSON.parse(message.data);
      if (role === "participante" && data.event === "answer_received") return;
      if (!reloadScheduled) {
        reloadScheduled = true;
        window.setTimeout(() => window.location.reload(), 250);
      }
    });
    socket.addEventListener("close", (event) => {
      if (event.code !== 4403) window.setTimeout(() => connect(gameId, role), 2000);
    });
  }

  function timer() {
    const element = document.querySelector(".timer[data-started]");
    if (!element) return;
    const publishForm = document.querySelector("form[data-auto-publish]");
    let publishing = false;
    const publishResults = () => {
      if (!publishForm || publishing) return;
      publishing = true;
      publishForm.querySelector("button")?.setAttribute("disabled", "disabled");
      publishForm.requestSubmit();
    };
    if (publishForm) {
      const answered = Number(publishForm.dataset.answered);
      const participants = Number(publishForm.dataset.participants);
      if (participants > 0 && answered >= participants) {
        window.setTimeout(publishResults, 500);
      }
    }
    const startedAt = new Date(element.dataset.started).getTime();
    const limit = Number(element.dataset.limit) * 1000;
    const update = () => {
      const remaining = Math.max(0, limit - (Date.now() - startedAt));
      element.textContent = `${Math.ceil(remaining / 1000)} s`;
      if (remaining <= 0) {
        document.querySelectorAll(".answer-button").forEach((button) => { button.disabled = true; });
        element.textContent = "Tiempo";
        publishResults();
        return;
      }
      window.setTimeout(update, 250);
    };
    update();
  }

  return {connect, timer};
})();

const QuestionBuilder = (() => {
  const settings = {
    multiple_choice: {minimum: 4, title: "Alternativas", help: "Registra cuatro alternativas y marca una o más como correctas.", typeHelp: "El participante selecciona todas las respuestas que considere correctas."},
    true_false: {minimum: 2, title: "Opciones", help: "Marca la respuesta correcta; al elegir una, la otra se desmarcará automáticamente.", typeHelp: "Una decisión rápida entre Verdadero y Falso."},
    short_answer: {minimum: 1, title: "Respuestas válidas", help: "Añade hasta diez palabras o frases que deben aceptarse.", typeHelp: "Se ignoran tildes, espacios repetidos y mayúsculas, salvo que actives la distinción de mayúsculas."},
    ordering: {minimum: 2, title: "Secuencia correcta", help: "Coloca los elementos en el orden correcto usando las flechas.", typeHelp: "El participante recibirá los elementos mezclados y deberá ordenarlos."},
    matching: {minimum: 2, title: "Parejas", help: "Completa ambas columnas para cada pareja.", typeHelp: "El participante vinculará cada elemento izquierdo con uno de la columna derecha."},
  };

  function init() {
    const builder = document.querySelector("#question-builder");
    if (!builder) return;
    const typeSelect = document.querySelector("#id_question_type");
    const list = document.querySelector("#component-list");
    const totalForms = document.querySelector("#id_options-TOTAL_FORMS");
    const maxForms = Number(document.querySelector("#id_options-MAX_NUM_FORMS").value);

    const rows = () => Array.from(list.querySelectorAll("[data-component-row]"));
    const hasData = (row) => Boolean(row.querySelector('[name$="-id"]')?.value || row.querySelector('[name$="-text"]')?.value.trim());
    const visibleRows = () => rows().filter((row) => !row.hidden && !row.querySelector('[name$="-DELETE"]')?.checked);

    function updateOrder() {
      visibleRows().forEach((row, index) => {
        row.querySelector(".component-number").textContent = index + 1;
        const order = row.querySelector('[name$="-order"]');
        if (order) order.value = index + 1;
      });
    }

    function wireRow(row) {
      row.querySelector(".move-up")?.addEventListener("click", () => {
        const previous = row.previousElementSibling;
        if (previous) list.insertBefore(row, previous);
        updateOrder();
      });
      row.querySelector(".move-down")?.addEventListener("click", () => {
        const next = row.nextElementSibling;
        if (next) list.insertBefore(next, row);
        updateOrder();
      });
      row.querySelector('[name$="-DELETE"]')?.addEventListener("change", (event) => {
        row.classList.toggle("component-deleted", event.target.checked);
        if (event.target.checked) {
          const radio = row.querySelector('[name="correct_component"]');
          if (radio) radio.checked = false;
        }
        updateOrder();
      });
    }

    function configure() {
      const type = typeSelect.value;
      const config = settings[type];
      const previousType = builder.dataset.currentType;
      if (previousType === "true_false" && type !== "true_false") {
        rows().slice(0, 2).forEach((row) => {
          const textInput = row.querySelector('[name$="-text"]');
          if (row.dataset.previousText !== undefined) textInput.value = row.dataset.previousText;
          textInput.readOnly = false;
          delete row.dataset.previousText;
        });
      }
      document.querySelector("#components-title").textContent = config.title;
      document.querySelector("#components-help").textContent = config.help;
      document.querySelector("#type-help").textContent = config.typeHelp;
      document.querySelector("#add-component").hidden = type === "true_false";
      document.querySelector(".case-sensitive-setting").hidden = type !== "short_answer";
      const usesCorrectOption = ["multiple_choice", "true_false"].includes(type);
      rows().forEach((row, index) => {
        const deleteInput = row.querySelector('[name$="-DELETE"]');
        if (type !== "true_false" && row.dataset.autoDeleted === "true") {
          if (deleteInput) deleteInput.checked = false;
          delete row.dataset.autoDeleted;
          row.classList.remove("component-deleted");
        }
        if (type === "true_false" && index >= 2) {
          if (row.querySelector('[name$="-id"]')?.value && deleteInput) {
            deleteInput.checked = true;
            row.dataset.autoDeleted = "true";
          }
          row.hidden = true;
        } else {
          row.hidden = index >= config.minimum && !hasData(row) && row.dataset.forceVisible !== "true";
        }
        row.querySelectorAll('[name$="-text"],[name$="-match_text"],[name$="-is_correct"],[name$="-order"]').forEach((control) => {
          control.disabled = row.hidden;
        });
        row.querySelector(".component-match").hidden = type !== "matching";
        row.querySelector(".component-correct").hidden = !usesCorrectOption;
        const correctCheckbox = row.querySelector('[name$="-is_correct"]');
        if (correctCheckbox) correctCheckbox.disabled = row.hidden || type !== "multiple_choice";
        row.querySelector(".correct-checkbox").hidden = type !== "multiple_choice";
        row.querySelector(".correct-radio").hidden = type !== "true_false";
        const correctRadio = row.querySelector('[name="correct_component"]');
        if (correctRadio) {
          correctRadio.disabled = row.hidden || !usesCorrectOption;
          if (type === "true_false" && index >= 2) correctRadio.checked = false;
        }
        row.querySelectorAll(".move-up,.move-down").forEach((button) => { button.hidden = !["ordering", "matching"].includes(type); });
      });
      if (type === "true_false") {
        const active = rows().filter((row) => !row.hidden).slice(0, 2);
        active.forEach((row, index) => {
          const textInput = row.querySelector('[name$="-text"]');
          if (previousType && previousType !== "true_false" && row.dataset.previousText === undefined) row.dataset.previousText = textInput.value;
          textInput.value = index === 0 ? "Verdadero" : "Falso";
          textInput.readOnly = true;
        });
      }
      builder.dataset.currentType = type;
      updateOrder();
    }

    rows().forEach(wireRow);
    document.querySelector("#add-component").addEventListener("click", () => {
      const hidden = rows().find((row) => row.hidden && !hasData(row));
      if (hidden) {
        hidden.hidden = false;
        hidden.dataset.forceVisible = "true";
      } else if (Number(totalForms.value) < maxForms) {
        const index = Number(totalForms.value);
        const html = document.querySelector("#empty-component-template").innerHTML.replaceAll("__prefix__", index);
        list.insertAdjacentHTML("beforeend", html);
        totalForms.value = index + 1;
        rows().at(-1).dataset.forceVisible = "true";
        wireRow(rows().at(-1));
      }
      configure();
    });
    typeSelect.addEventListener("change", configure);
    builder.addEventListener("submit", updateOrder);
    configure();
  }

  return {init};
})();

function initOrderingAnswer() {
  const list = document.querySelector("#ordering-list");
  const hidden = document.querySelector("#ordered-ids");
  if (!list || !hidden) return;
  const update = () => { hidden.value = JSON.stringify(Array.from(list.children).map((item) => Number(item.dataset.optionId))); };
  list.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-direction]");
    if (!button) return;
    const item = button.closest("[data-option-id]");
    if (button.dataset.direction === "up" && item.previousElementSibling) list.insertBefore(item, item.previousElementSibling);
    if (button.dataset.direction === "down" && item.nextElementSibling) list.insertBefore(item.nextElementSibling, item);
    update();
  });
  update();
}

function initAvatarSelector() {
  const selector = document.querySelector("#avatar-selector");
  if (!selector) return;
  const buttons = document.querySelectorAll("[data-avatar-filter]");
  const choices = selector.querySelectorAll("[data-avatar-category]");
  buttons.forEach((button) => button.addEventListener("click", () => {
    const category = button.dataset.avatarFilter;
    buttons.forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.classList.toggle("btn-dark", active);
      item.classList.toggle("btn-outline-dark", !active);
      item.setAttribute("aria-pressed", String(active));
    });
    choices.forEach((choice) => {
      choice.hidden = category !== "all" && choice.dataset.avatarCategory !== category;
    });
  }));
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("#answer-form");
  if (form) form.addEventListener("submit", (event) => {
    if (form.dataset.answerMode === "choice") {
      const selectedButton = event.submitter;
      if (!selectedButton || !selectedButton.value) {
        event.preventDefault();
        return;
      }
      const selectedOption = document.createElement("input");
      selectedOption.type = "hidden";
      selectedOption.name = "option";
      selectedOption.value = selectedButton.value;
      form.appendChild(selectedOption);
    }
    form.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  });
  initOrderingAnswer();
  initAvatarSelector();
});
