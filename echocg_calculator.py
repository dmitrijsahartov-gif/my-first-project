#!/usr/bin/env python3
"""
Калькулятор основных показателей эхокардиографии (ЭхоКГ).

Удобен для телефона: все данные вводятся одним сообщением
в формате «Параметр: значение», затем сразу выводится полный расчёт.

Рассчитывает:
  - площадь поверхности тела (ППТ, формула Мостеллера);
  - фракцию выброса ЛЖ (по готовым объёмам или по Teichholz);
  - ударный объём и индексированный ударный объём;
  - минутный объём кровообращения (МОС) и сердечный индекс (СИ);
  - массу миокарда ЛЖ (формула ASE);
  - индексированную массу миокарда ЛЖ;
  - относительную толщину стенок (ОТС).

Результаты можно сохранить в текстовый файл.
"""

from __future__ import annotations

import math
import re
import sys
from datetime import datetime
from pathlib import Path


# Нормы массы миокарда ЛЖ по рекомендациям ASE (ориентиры для взрослых).
LV_MASS_NORMS = {
    "м": {
        "label": "мужчин",
        "sex_name": "мужской",
        "mass_max_g": 224.0,
        "lvmi_max": 115.0,
    },
    "ж": {
        "label": "женщин",
        "sex_name": "женский",
        "mass_max_g": 162.0,
        "lvmi_max": 95.0,
    },
}

# Канонические поля и допустимые названия в сообщении.
FIELD_ALIASES: dict[str, str] = {
    "пол": "sex",
    "рост": "height_cm",
    "вес": "weight_kg",
    "масса": "weight_kg",
    "масса тела": "weight_kg",
    "чсс": "hr_bpm",
    "пульс": "hr_bpm",
    "кдр": "lvidd_mm",
    "кдр лж": "lvidd_mm",
    "кср": "lvids_mm",
    "кср лж": "lvids_mm",
    "тмжп": "ivsd_mm",
    "мжп": "ivsd_mm",
    "мжпд": "ivsd_mm",
    "тмжпд": "ivsd_mm",
    "тзслж": "pwtd_mm",
    "тзс": "pwtd_mm",
    "тзсд": "pwtd_mm",
    "зслж": "pwtd_mm",
    "зсд": "pwtd_mm",
    "зс": "pwtd_mm",
    "кдо": "edv_ml",
    "кдо лж": "edv_ml",
    "ксо": "esv_ml",
    "ксо лж": "esv_ml",
}

EXAMPLE_SIZES = """\
Пол: муж
Рост: 178
Вес: 86
КДР: 52
КСР: 34
ТМЖП: 11
ТЗСЛЖ: 10
ЧСС: 68"""

EXAMPLE_VOLUMES = """\
Пол: жен
Рост: 165
Вес: 60
КДР: 46
ТМЖП: 9
ТЗСЛЖ: 9
КДО: 100
КСО: 40
ЧСС: 70"""


# ---------------------------------------------------------------------------
# Парсинг одного сообщения
# ---------------------------------------------------------------------------

def normalize_key(raw: str) -> str:
    key = raw.strip().lower().replace("ё", "е")
    key = key.replace("_", " ")
    key = re.sub(r"\s+", " ", key)
    return key


def parse_number(raw: str) -> float:
    text = raw.strip().lower().replace(",", ".")
    text = re.sub(r"(см|мм|мл|кг|уд/?мин|уд|bpm|%|г/м²|г)$", "", text).strip()
    text = text.replace(" ", "")
    return float(text)


def parse_sex(raw: str) -> str:
    value = raw.strip().lower().replace("ё", "е")
    if value in {"м", "m", "муж", "мужской", "male", "man"}:
        return "м"
    if value in {"ж", "f", "жен", "женский", "female", "woman"}:
        return "ж"
    raise ValueError(f"непонятный пол «{raw}» (ожидается муж/жен)")


def parse_message(text: str) -> dict[str, float | str]:
    """Разбирает блок «Ключ: значение» в словарь канонических полей."""
    data: dict[str, float | str] = {}
    unknown: list[str] = []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line and "—" not in line and "-" not in line:
            continue

        # Разделитель: двоеточие, длинное/короткое тире.
        parts = re.split(r"\s*[:—–-]\s*", line, maxsplit=1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            continue

        key = normalize_key(parts[0])
        value_raw = parts[1].strip()
        field = FIELD_ALIASES.get(key)
        if field is None:
            unknown.append(parts[0].strip())
            continue

        if field == "sex":
            data[field] = parse_sex(value_raw)
        else:
            data[field] = parse_number(value_raw)

    if unknown:
        names = ", ".join(unknown)
        raise ValueError(f"неизвестные поля: {names}")

    return data


def validate_data(data: dict[str, float | str]) -> list[str]:
    """Проверяет обязательные поля и режим объёмов/размеров."""
    errors: list[str] = []
    required = ["sex", "height_cm", "weight_kg", "hr_bpm", "lvidd_mm", "ivsd_mm", "pwtd_mm"]
    labels = {
        "sex": "Пол",
        "height_cm": "Рост",
        "weight_kg": "Вес",
        "hr_bpm": "ЧСС",
        "lvidd_mm": "КДР",
        "ivsd_mm": "ТМЖП",
        "pwtd_mm": "ТЗСЛЖ",
    }
    for field in required:
        if field not in data:
            errors.append(f"не указано поле «{labels[field]}»")

    has_volumes = "edv_ml" in data or "esv_ml" in data
    has_esd = "lvids_mm" in data

    if has_volumes:
        if "edv_ml" not in data or "esv_ml" not in data:
            errors.append("для режима объёмов нужны оба поля: КДО и КСО")
    elif not has_esd:
        errors.append(
            "укажите либо КСР (расчёт по размерам), либо КДО и КСО (готовые объёмы)"
        )

    for field, label, minimum in (
        ("height_cm", "Рост", 0),
        ("weight_kg", "Вес", 0),
        ("hr_bpm", "ЧСС", 0),
        ("lvidd_mm", "КДР", 0),
        ("lvids_mm", "КСР", 0),
        ("ivsd_mm", "ТМЖП", 0),
        ("pwtd_mm", "ТЗСЛЖ", 0),
        ("edv_ml", "КДО", 0),
        ("esv_ml", "КСО", 0),
    ):
        if field in data and isinstance(data[field], (int, float)) and data[field] <= minimum:
            errors.append(f"«{label}» должно быть больше {minimum}")

    if "lvidd_mm" in data and "lvids_mm" in data:
        if data["lvidd_mm"] <= data["lvids_mm"]:  # type: ignore[operator]
            errors.append("КДР должен быть больше КСР")

    if "edv_ml" in data and "esv_ml" in data:
        if data["edv_ml"] <= data["esv_ml"]:  # type: ignore[operator]
            errors.append("КДО должен быть больше КСО")

    return errors


# ---------------------------------------------------------------------------
# Расчёты
# ---------------------------------------------------------------------------

def body_surface_area(height_cm: float, weight_kg: float) -> float:
    return math.sqrt((height_cm * weight_kg) / 3600.0)


def teichholz_volume(diameter_cm: float) -> float:
    return (7.0 * diameter_cm**3) / (2.4 + diameter_cm)


def stroke_volume(edv_ml: float, esv_ml: float) -> float:
    if edv_ml <= esv_ml:
        raise ValueError("КДО должен быть больше КСО.")
    return edv_ml - esv_ml


def indexed_stroke_volume(sv_ml: float, bsa_m2: float) -> float:
    return sv_ml / bsa_m2


def ejection_fraction(edv_ml: float, esv_ml: float) -> float:
    return (stroke_volume(edv_ml, esv_ml) / edv_ml) * 100.0


def cardiac_output(sv_ml: float, hr_bpm: float) -> float:
    return (sv_ml * hr_bpm) / 1000.0


def cardiac_index(co_l_min: float, bsa_m2: float) -> float:
    return co_l_min / bsa_m2


def lv_mass_ase(ivsd_cm: float, lvidd_cm: float, pwtd_cm: float) -> float:
    cube_sum = (ivsd_cm + lvidd_cm + pwtd_cm) ** 3
    cube_cavity = lvidd_cm**3
    return 0.8 * (1.04 * (cube_sum - cube_cavity)) + 0.6


def indexed_lv_mass(mass_g: float, bsa_m2: float) -> float:
    return mass_g / bsa_m2


def relative_wall_thickness(pwtd_cm: float, lvidd_cm: float) -> float:
    return (2.0 * pwtd_cm) / lvidd_cm


def norms_for_sex(sex: str) -> dict:
    return LV_MASS_NORMS[sex]


def compute(data: dict[str, float | str]) -> dict:
    """Считает все показатели из разобранных данных."""
    sex = str(data["sex"])
    height_cm = float(data["height_cm"])
    weight_kg = float(data["weight_kg"])
    hr_bpm = float(data["hr_bpm"])
    lvidd_mm = float(data["lvidd_mm"])
    ivsd_mm = float(data["ivsd_mm"])
    pwtd_mm = float(data["pwtd_mm"])

    lvidd_cm = lvidd_mm / 10.0
    ivsd_cm = ivsd_mm / 10.0
    pwtd_cm = pwtd_mm / 10.0

    if "edv_ml" in data and "esv_ml" in data:
        edv_ml = float(data["edv_ml"])
        esv_ml = float(data["esv_ml"])
        volume_source = "готовые объёмы КДО/КСО"
    else:
        lvids_cm = float(data["lvids_mm"]) / 10.0
        edv_ml = teichholz_volume(lvidd_cm)
        esv_ml = teichholz_volume(lvids_cm)
        volume_source = "Teichholz (КДР/КСР)"

    bsa = body_surface_area(height_cm, weight_kg)
    ef = ejection_fraction(edv_ml, esv_ml)
    sv_ml = stroke_volume(edv_ml, esv_ml)
    svi = indexed_stroke_volume(sv_ml, bsa)
    co = cardiac_output(sv_ml, hr_bpm)
    ci = cardiac_index(co, bsa)
    mass = lv_mass_ase(ivsd_cm, lvidd_cm, pwtd_cm)
    lvmi = indexed_lv_mass(mass, bsa)
    rwt = relative_wall_thickness(pwtd_cm, lvidd_cm)

    return {
        "sex": sex,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "hr_bpm": hr_bpm,
        "lvidd_mm": lvidd_mm,
        "ivsd_mm": ivsd_mm,
        "pwtd_mm": pwtd_mm,
        "lvids_mm": float(data["lvids_mm"]) if "lvids_mm" in data else None,
        "bsa": bsa,
        "ef": ef,
        "volume_source": volume_source,
        "edv_ml": edv_ml,
        "esv_ml": esv_ml,
        "sv_ml": sv_ml,
        "svi": svi,
        "co": co,
        "ci": ci,
        "mass": mass,
        "lvmi": lvmi,
        "rwt": rwt,
    }


# ---------------------------------------------------------------------------
# Интерпретация
# ---------------------------------------------------------------------------

def interpret_ef(ef: float) -> tuple[str, str]:
    if ef >= 55:
        return "норма", "≥ 55%"
    if ef >= 45:
        return "снижена", "лёгкое ↓ 45–54%"
    if ef >= 30:
        return "снижена", "умеренное ↓ 30–44%"
    return "снижена", "выраженное ↓ < 30%"


def interpret_stroke_volume(sv_ml: float) -> tuple[str, str]:
    ref = "ориентир 60–100 мл"
    if sv_ml < 60:
        return "снижен", ref
    if sv_ml > 100:
        return "повышен", ref
    return "норма", ref


def interpret_svi(svi: float) -> tuple[str, str]:
    ref = "ориентир 33–47 мл/м²"
    if svi < 33:
        return "снижен", ref
    if svi > 47:
        return "повышен", ref
    return "норма", ref


def interpret_ci(ci: float) -> tuple[str, str]:
    ref = "ориентир 2,5–4,0 л/мин/м²"
    if ci < 2.5:
        return "снижен", ref
    if ci > 4.0:
        return "повышен", ref
    return "норма", ref


def interpret_lv_mass(mass_g: float, sex: str) -> tuple[str, str]:
    norms = norms_for_sex(sex)
    limit = norms["mass_max_g"]
    ref = f"≤ {limit:g} г ({norms['label']})"
    if mass_g > limit:
        return "выше нормы", ref
    return "норма", ref


def interpret_lvmi(lvmi: float, sex: str) -> tuple[str, str]:
    norms = norms_for_sex(sex)
    limit = norms["lvmi_max"]
    ref = f"≤ {limit:g} г/м² ({norms['label']})"
    if lvmi > limit:
        return "гипертрофия", ref
    return "норма", ref


def interpret_rwt(rwt: float) -> tuple[str, str]:
    if rwt > 0.42:
        return "повышена", "≤ 0,42; концентрический тип"
    return "норма", "≤ 0,42; эксцентрический / норма"


def status_mark(assessment: str) -> str:
    if assessment in {"", "—"}:
        return "·"
    if assessment == "норма":
        return "✓"
    return "!"


# ---------------------------------------------------------------------------
# Оформление и сохранение
# ---------------------------------------------------------------------------

WIDTH = 80


def hline(char: str = "─") -> str:
    return char * WIDTH


def center_title(text: str) -> str:
    return f" {text} ".center(WIDTH, "─")


def format_row(name: str, value: str, assessment: str = "", note: str = "") -> str:
    mark = status_mark(assessment)
    left = f"{mark} {name}"
    return f"  {left:<27} {value:>16}  {assessment:<14} {note}"


def build_report(r: dict) -> str:
    sex = r["sex"]
    norms = norms_for_sex(sex)
    ef_s, ef_n = interpret_ef(r["ef"])
    sv_s, sv_n = interpret_stroke_volume(r["sv_ml"])
    svi_s, svi_n = interpret_svi(r["svi"])
    ci_s, ci_n = interpret_ci(r["ci"])
    mass_s, mass_n = interpret_lv_mass(r["mass"], sex)
    lvmi_s, lvmi_n = interpret_lvmi(r["lvmi"], sex)
    rwt_s, rwt_n = interpret_rwt(r["rwt"])

    input_lines = [
        f"  КДР {r['lvidd_mm']:g} мм, ТМЖП {r['ivsd_mm']:g} мм, ТЗСЛЖ {r['pwtd_mm']:g} мм",
    ]
    if r["lvids_mm"] is not None:
        input_lines.append(f"  КСР {r['lvids_mm']:g} мм")
    if r["volume_source"].startswith("готовые"):
        input_lines.append(f"  КДО {r['edv_ml']:g} мл, КСО {r['esv_ml']:g} мл")

    lines: list[str] = [
        hline("═"),
        "РЕЗУЛЬТАТЫ ЭхоКГ".center(WIDTH),
        hline("═"),
        "",
        center_title("Пациент"),
        f"  Пол:     {norms['sex_name']}",
        f"  Рост:    {r['height_cm']:g} см",
        f"  Вес:     {r['weight_kg']:g} кг",
        f"  ЧСС:     {r['hr_bpm']:g} уд/мин",
        (
            f"  Нормы ММЛЖ ({norms['label']}): "
            f"≤ {norms['mass_max_g']:g} г / ≤ {norms['lvmi_max']:g} г/м²"
        ),
        "",
        center_title("Исходные измерения"),
        *input_lines,
        f"  Объёмы:  {r['volume_source']}",
        "",
        center_title("Антропометрия и насосная функция"),
        f"  {'Показатель':<25} {'Значение':>16}  {'Оценка':<14} Пояснение",
        f"  {'-' * 25} {'-' * 16}  {'-' * 14} {'-' * 24}",
        format_row("ППТ", f"{r['bsa']:.2f} м²", "—", "формула Мостеллера"),
        format_row("ФВ ЛЖ", f"{r['ef']:.1f} %", ef_s, ef_n),
        format_row("  КДО", f"{r['edv_ml']:.1f} мл"),
        format_row("  КСО", f"{r['esv_ml']:.1f} мл"),
        format_row("УО", f"{r['sv_ml']:.1f} мл", sv_s, f"{sv_n}; КДО − КСО"),
        format_row("ИУО", f"{r['svi']:.1f} мл/м²", svi_s, f"{svi_n}; УО / ППТ"),
        format_row("МОС", f"{r['co']:.2f} л/мин", "—", "УО × ЧСС / 1000"),
        format_row("СИ", f"{r['ci']:.2f} л/мин/м²", ci_s, f"{ci_n}; МОС / ППТ"),
        "",
        center_title("Масса миокарда и геометрия ЛЖ"),
        f"  {'Показатель':<25} {'Значение':>16}  {'Оценка':<14} Пояснение",
        f"  {'-' * 25} {'-' * 16}  {'-' * 14} {'-' * 24}",
        format_row("ММЛЖ (ASE)", f"{r['mass']:.1f} г", mass_s, mass_n),
        format_row("ИММЛЖ", f"{r['lvmi']:.1f} г/м²", lvmi_s, lvmi_n),
        format_row("ОТС", f"{r['rwt']:.2f}", rwt_s, rwt_n),
        "",
        center_title("Сводка"),
    ]

    flags: list[str] = []
    for name, status in (
        ("ФВ", ef_s),
        ("УО", sv_s),
        ("ИУО", svi_s),
        ("СИ", ci_s),
        ("ММЛЖ", mass_s),
        ("ИММЛЖ", lvmi_s),
        ("ОТС", rwt_s),
    ):
        if status not in {"норма", "—"}:
            flags.append(f"{name}: {status}")

    if flags:
        lines.append("  Отклонения: " + "; ".join(flags) + ".")
    else:
        lines.append("  Основные показатели в пределах ориентировочных норм.")
    lines.extend(
        [
            "  Интерпретация ориентировочная; заключение формирует врач.",
            "  Обозначения: ✓ норма · справочно ! отклонение",
            hline("═"),
        ]
    )
    return "\n".join(lines)


def default_report_filename() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"echocg_rezultat_{stamp}.txt")


def maybe_save_report(report: str) -> Path | None:
    """Спрашивает про сохранение только в интерактивном режиме."""
    if not sys.stdin.isatty():
        return None
    answer = input("\nСохранить результат в файл? (да/нет): ").strip().lower()
    if answer not in {"д", "да", "y", "yes"}:
        return None

    suggested = default_report_filename()
    raw = input(f"Имя файла [{suggested.name}]: ").strip()
    path = Path(raw) if raw else suggested
    if path.suffix.lower() != ".txt":
        path = path.with_suffix(".txt")

    header = (
        f"Калькулятор ЭхоКГ\n"
        f"Дата и время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"{hline('─')}\n"
    )
    path.write_text(header + report + "\n", encoding="utf-8")
    return path.resolve()


def print_help() -> None:
    print(hline("═"))
    print("Калькулятор ЭхоКГ — ввод одним сообщением".center(WIDTH))
    print(hline("═"))
    print(
        """
Вставьте все данные одним блоком и отправьте пустую строку
(или Ctrl+D / Ctrl+Z), чтобы получить расчёт.

Размеры ЛЖ — в мм, объёмы — в мл, рост — в см, вес — в кг.

Режим 1 — по размерам (КДР + КСР), объёмы считаются по Teichholz:
""".rstrip()
    )
    print()
    print(EXAMPLE_SIZES)
    print(
        """
Режим 2 — готовые объёмы (КДО + КСО). КДР, ТМЖП и ТЗСЛЖ всё равно
нужны для массы миокарда и ОТС:
""".rstrip()
    )
    print()
    print(EXAMPLE_VOLUMES)
    print()
    print("Можно также передать файл:  python3 echocg_calculator.py данные.txt")
    print(hline("─"))


def read_message_from_stdin() -> str:
    """Читает сообщение: до EOF или до первой полностью пустой строки после данных."""
    lines: list[str] = []
    saw_content = False
    for line in sys.stdin:
        if line.strip() == "":
            if saw_content:
                break
            continue
        saw_content = True
        lines.append(line.rstrip("\n"))
    return "\n".join(lines)


def read_input_text(argv: list[str]) -> str:
    if len(argv) >= 2:
        if argv[1] in {"-h", "--help", "помощь", "help"}:
            print_help()
            raise SystemExit(0)
        path = Path(argv[1])
        if not path.is_file():
            raise FileNotFoundError(f"файл не найден: {path}")
        return path.read_text(encoding="utf-8")

    if sys.stdin.isatty():
        print_help()
        print("Вставьте данные и нажмите Enter на пустой строке:\n")

    text = read_message_from_stdin()
    if not text.strip():
        raise ValueError("пустое сообщение — нечего считать")
    return text


# ---------------------------------------------------------------------------
# Главный сценарий
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    try:
        text = read_input_text(argv)
        data = parse_message(text)
        errors = validate_data(data)
        if errors:
            print("Не удалось разобрать данные:")
            for err in errors:
                print(f"  • {err}")
            print("\nПример правильного формата:")
            print(EXAMPLE_SIZES)
            return 1
        result = compute(data)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Ошибка: {exc}")
        print("\nСправка: python3 echocg_calculator.py --help")
        return 1

    report = build_report(result)
    print()
    print(report)

    saved = maybe_save_report(report)
    if saved is not None:
        print(f"\nФайл сохранён: {saved}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nРасчёт прерван пользователем.")
        raise SystemExit(130)
    except EOFError:
        print("\nВвод завершён досрочно.")
        raise SystemExit(1)
