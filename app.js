const EXAMPLE_SIZES = `Пол: муж
Рост: 178
Вес: 86
КДР: 52
КСР: 34
ТМЖП: 11
ТЗСЛЖ: 10
ЧСС: 68`;

const EXAMPLE_VOLUMES = `Пол: жен
Рост: 165
Вес: 60
КДР: 46
ТМЖП: 9
ТЗСЛЖ: 9
КДО: 100
КСО: 40
ЧСС: 70`;

const FIELD_ALIASES = {
  пол: "sex",
  рост: "height_cm",
  вес: "weight_kg",
  масса: "weight_kg",
  "масса тела": "weight_kg",
  чсс: "hr_bpm",
  пульс: "hr_bpm",
  кдр: "lvidd_mm",
  "кдр лж": "lvidd_mm",
  кср: "lvids_mm",
  "кср лж": "lvids_mm",
  тмжп: "ivsd_mm",
  мжп: "ivsd_mm",
  мжпд: "ivsd_mm",
  тмжпд: "ivsd_mm",
  тзслж: "pwtd_mm",
  тзс: "pwtd_mm",
  тзсд: "pwtd_mm",
  зслж: "pwtd_mm",
  зсд: "pwtd_mm",
  зс: "pwtd_mm",
  кдо: "edv_ml",
  "кдо лж": "edv_ml",
  ксо: "esv_ml",
  "ксо лж": "esv_ml",
};

const LV_MASS_NORMS = {
  м: { label: "мужчин", sexName: "мужской", massMax: 224, lvmiMax: 115 },
  ж: { label: "женщин", sexName: "женский", massMax: 162, lvmiMax: 95 },
};

function normalizeKey(raw) {
  return raw
    .trim()
    .toLowerCase()
    .replaceAll("ё", "е")
    .replaceAll("_", " ")
    .replace(/\s+/g, " ");
}

function parseNumber(raw) {
  let text = String(raw).trim().toLowerCase().replace(",", ".");
  text = text.replace(/(см|мм|мл|кг|уд\/?мин|уд|bpm|%|г\/м²|г)$/i, "").trim();
  text = text.replace(/\s+/g, "");
  const value = Number(text);
  if (!Number.isFinite(value)) throw new Error(`не число: «${raw}»`);
  return value;
}

function parseSex(raw) {
  const value = String(raw).trim().toLowerCase().replaceAll("ё", "е");
  if (["м", "m", "муж", "мужской", "male", "man"].includes(value)) return "м";
  if (["ж", "f", "жен", "женский", "female", "woman"].includes(value)) return "ж";
  throw new Error(`непонятный пол «${raw}» (ожидается муж/жен)`);
}

function parseMessage(text) {
  const data = {};
  const unknown = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const match = line.match(/^([^:—–-]+?)\s*[:—–-]\s*(.+)$/);
    if (!match) continue;
    const key = normalizeKey(match[1]);
    const field = FIELD_ALIASES[key];
    if (!field) {
      unknown.push(match[1].trim());
      continue;
    }
    data[field] = field === "sex" ? parseSex(match[2]) : parseNumber(match[2]);
  }
  if (unknown.length) throw new Error(`неизвестные поля: ${unknown.join(", ")}`);
  return data;
}

function validateData(data) {
  const errors = [];
  const required = {
    sex: "Пол",
    height_cm: "Рост",
    weight_kg: "Вес",
    hr_bpm: "ЧСС",
    lvidd_mm: "КДР",
    ivsd_mm: "ТМЖП",
    pwtd_mm: "ТЗСЛЖ",
  };
  for (const [field, label] of Object.entries(required)) {
    if (!(field in data)) errors.push(`не указано поле «${label}»`);
  }

  const hasVolumes = "edv_ml" in data || "esv_ml" in data;
  const hasEsd = "lvids_mm" in data;
  if (hasVolumes) {
    if (!("edv_ml" in data) || !("esv_ml" in data)) {
      errors.push("для режима объёмов нужны оба поля: КДО и КСО");
    }
  } else if (!hasEsd) {
    errors.push("укажите либо КСР (по размерам), либо КДО и КСО");
  }

  for (const [field, label] of [
    ["height_cm", "Рост"],
    ["weight_kg", "Вес"],
    ["hr_bpm", "ЧСС"],
    ["lvidd_mm", "КДР"],
    ["lvids_mm", "КСР"],
    ["ivsd_mm", "ТМЖП"],
    ["pwtd_mm", "ТЗСЛЖ"],
    ["edv_ml", "КДО"],
    ["esv_ml", "КСО"],
  ]) {
    if (field in data && data[field] <= 0) errors.push(`«${label}» должно быть больше 0`);
  }

  if ("lvidd_mm" in data && "lvids_mm" in data && data.lvidd_mm <= data.lvids_mm) {
    errors.push("КДР должен быть больше КСР");
  }
  if ("edv_ml" in data && "esv_ml" in data && data.edv_ml <= data.esv_ml) {
    errors.push("КДО должен быть больше КСО");
  }
  return errors;
}

function teichholzVolume(diameterCm) {
  return (7 * diameterCm ** 3) / (2.4 + diameterCm);
}

function compute(data) {
  const lviddCm = data.lvidd_mm / 10;
  const ivsdCm = data.ivsd_mm / 10;
  const pwtdCm = data.pwtd_mm / 10;

  let edv;
  let esv;
  let volumeSource;
  if ("edv_ml" in data && "esv_ml" in data) {
    edv = data.edv_ml;
    esv = data.esv_ml;
    volumeSource = "готовые объёмы КДО/КСО";
  } else {
    edv = teichholzVolume(lviddCm);
    esv = teichholzVolume(data.lvids_mm / 10);
    volumeSource = "Teichholz (КДР/КСР)";
  }

  const bsa = Math.sqrt((data.height_cm * data.weight_kg) / 3600);
  const sv = edv - esv;
  const ef = (sv / edv) * 100;
  const svi = sv / bsa;
  const co = (sv * data.hr_bpm) / 1000;
  const ci = co / bsa;
  const mass =
    0.8 * (1.04 * ((ivsdCm + lviddCm + pwtdCm) ** 3 - lviddCm ** 3)) + 0.6;
  const lvmi = mass / bsa;
  const rwt = (2 * pwtdCm) / lviddCm;

  return {
    ...data,
    volumeSource,
    edv,
    esv,
    bsa,
    ef,
    sv,
    svi,
    co,
    ci,
    mass,
    lvmi,
    rwt,
  };
}

function interpretEf(ef) {
  if (ef >= 55) return ["норма", "≥ 55%"];
  if (ef >= 45) return ["снижена", "лёгкое ↓ 45–54%"];
  if (ef >= 30) return ["снижена", "умеренное ↓ 30–44%"];
  return ["снижена", "выраженное ↓ < 30%"];
}

function interpretSv(sv) {
  const ref = "ориентир 60–100 мл";
  if (sv < 60) return ["снижен", ref];
  if (sv > 100) return ["повышен", ref];
  return ["норма", ref];
}

function interpretSvi(svi) {
  const ref = "ориентир 33–47 мл/м²";
  if (svi < 33) return ["снижен", ref];
  if (svi > 47) return ["повышен", ref];
  return ["норма", ref];
}

function interpretCi(ci) {
  const ref = "ориентир 2,5–4,0 л/мин/м²";
  if (ci < 2.5) return ["снижен", ref];
  if (ci > 4.0) return ["повышен", ref];
  return ["норма", ref];
}

function interpretMass(mass, sex) {
  const n = LV_MASS_NORMS[sex];
  const ref = `≤ ${n.massMax} г (${n.label})`;
  return mass > n.massMax ? ["выше нормы", ref] : ["норма", ref];
}

function interpretLvmi(lvmi, sex) {
  const n = LV_MASS_NORMS[sex];
  const ref = `≤ ${n.lvmiMax} г/м² (${n.label})`;
  return lvmi > n.lvmiMax ? ["гипертрофия", ref] : ["норма", ref];
}

function interpretRwt(rwt) {
  if (rwt > 0.42) return ["повышена", "≤ 0,42; концентрический тип"];
  return ["норма", "≤ 0,42; эксцентрический / норма"];
}

function badge(status) {
  if (status === "норма") return `<span class="badge badge-ok">${status}</span>`;
  if (status === "—" || !status) return `<span class="badge badge-muted">—</span>`;
  return `<span class="badge badge-warn">${status}</span>`;
}

function row(name, value, status = "", note = "") {
  return `<tr>
    <td>${name}</td>
    <td>${value}</td>
    <td>${badge(status || "—")}</td>
    <td>${note}</td>
  </tr>`;
}

function renderResults(r) {
  const norms = LV_MASS_NORMS[r.sex];
  const [efS, efN] = interpretEf(r.ef);
  const [svS, svN] = interpretSv(r.sv);
  const [sviS, sviN] = interpretSvi(r.svi);
  const [ciS, ciN] = interpretCi(r.ci);
  const [massS, massN] = interpretMass(r.mass, r.sex);
  const [lvmiS, lvmiN] = interpretLvmi(r.lvmi, r.sex);
  const [rwtS, rwtN] = interpretRwt(r.rwt);

  const flags = [];
  for (const [name, status] of [
    ["ФВ", efS],
    ["УО", svS],
    ["ИУО", sviS],
    ["СИ", ciS],
    ["ММЛЖ", massS],
    ["ИММЛЖ", lvmiS],
    ["ОТС", rwtS],
  ]) {
    if (status !== "норма") flags.push(`${name}: ${status}`);
  }

  const meta = [
    `Пол: ${norms.sexName}`,
    `Рост ${r.height_cm} см · вес ${r.weight_kg} кг · ЧСС ${r.hr_bpm} уд/мин`,
    `КДР ${r.lvidd_mm} мм · ТМЖП ${r.ivsd_mm} мм · ТЗСЛЖ ${r.pwtd_mm} мм`,
    r.lvids_mm != null ? `КСР ${r.lvids_mm} мм` : null,
    r.volumeSource.startsWith("готовые")
      ? `КДО ${r.edv} мл · КСО ${r.esv} мл`
      : null,
    `Объёмы: ${r.volumeSource}`,
    `Нормы ММЛЖ (${norms.label}): ≤ ${norms.massMax} г / ≤ ${norms.lvmiMax} г/м²`,
  ]
    .filter(Boolean)
    .map((x) => `<div>${x}</div>`)
    .join("");

  const tableHead = `<thead><tr><th>Показатель</th><th>Значение</th><th>Оценка</th><th>Пояснение</th></tr></thead>`;

  document.getElementById("results").innerHTML = `
    <h2>Результаты</h2>
    <div class="meta">${meta}</div>
    <div class="section-label">Насосная функция</div>
    <table class="table">${tableHead}<tbody>
      ${row("ППТ", `${r.bsa.toFixed(2)} м²`, "—", "формула Мостеллера")}
      ${row("ФВ ЛЖ", `${r.ef.toFixed(1)} %`, efS, efN)}
      ${row("КДО", `${r.edv.toFixed(1)} мл`)}
      ${row("КСО", `${r.esv.toFixed(1)} мл`)}
      ${row("УО", `${r.sv.toFixed(1)} мл`, svS, `${svN}; КДО − КСО`)}
      ${row("ИУО", `${r.svi.toFixed(1)} мл/м²`, sviS, `${sviN}; УО / ППТ`)}
      ${row("МОС", `${r.co.toFixed(2)} л/мин`, "—", "УО × ЧСС / 1000")}
      ${row("СИ", `${r.ci.toFixed(2)} л/мин/м²`, ciS, `${ciN}; МОС / ППТ`)}
    </tbody></table>
    <div class="section-label">Масса и геометрия</div>
    <table class="table">${tableHead}<tbody>
      ${row("ММЛЖ (ASE)", `${r.mass.toFixed(1)} г`, massS, massN)}
      ${row("ИММЛЖ", `${r.lvmi.toFixed(1)} г/м²`, lvmiS, lvmiN)}
      ${row("ОТС", r.rwt.toFixed(2), rwtS, rwtN)}
    </tbody></table>
    <div class="summary">
      ${
        flags.length
          ? `<strong>Отклонения:</strong> ${flags.join("; ")}.`
          : "Основные показатели в пределах ориентировочных норм."
      }
      <div class="footer-note">Интерпретация ориентировочная; заключение формирует врач.</div>
    </div>
  `;
  document.getElementById("results").classList.add("show");
}

function showError(message) {
  const el = document.getElementById("error");
  el.textContent = message;
  el.classList.add("show");
  document.getElementById("results").classList.remove("show");
}

function clearError() {
  const el = document.getElementById("error");
  el.textContent = "";
  el.classList.remove("show");
}

function calculate() {
  clearError();
  const text = document.getElementById("input").value;
  try {
    const data = parseMessage(text);
    const errors = validateData(data);
    if (errors.length) {
      showError("Не удалось разобрать данные:\n• " + errors.join("\n• "));
      return;
    }
    renderResults(compute(data));
    document.getElementById("results").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showError(`Ошибка: ${err.message}`);
  }
}

function pasteExample(kind) {
  document.getElementById("input").value = kind === "volumes" ? EXAMPLE_VOLUMES : EXAMPLE_SIZES;
  clearError();
}

let deferredPrompt = null;

function setupInstall() {
  const tip = document.getElementById("installTip");
  const btn = document.getElementById("installBtn");

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    tip.classList.add("show");
    btn.hidden = false;
  });

  btn.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    btn.hidden = true;
  });

  // iOS tip
  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const isStandalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  if (isIos && !isStandalone) tip.classList.add("show");
}

document.getElementById("calcBtn").addEventListener("click", calculate);
document.getElementById("exampleSizesBtn").addEventListener("click", () => pasteExample("sizes"));
document.getElementById("exampleVolumesBtn").addEventListener("click", () => pasteExample("volumes"));
setupInstall();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}
