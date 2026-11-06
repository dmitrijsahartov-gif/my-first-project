#!/usr/bin/env python3
"""
Калькулятор основных показателей эхокардиографии (ЭхоКГ).

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


# ---------------------------------------------------------------------------
# Ввод
# ---------------------------------------------------------------------------

def read_float(prompt: str, *, minimum: float | None = None) -> float:
    """Читает число с повторным запросом при ошибке."""
    while True:
        raw = input(prompt).strip().replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            print("  ! Ошибка: введите число (например, 70 или 4,5).")
            continue
        if minimum is not None and value <= minimum:
            print(f"  ! Ошибка: значение должно быть больше {minimum}.")
            continue
        return value


def ask_choice(prompt: str, options: dict[str, str]) -> str:
    """Спрашивает вариант из словаря {ключ: описание}."""
    print(prompt)
    for key, title in options.items():
        print(f"  {key} — {title}")
    keys = set(options)
    while True:
        choice = input("Выберите: ").strip()
        if choice in keys:
            return choice
        print(f"  ! Ошибка: введите одно из: {', '.join(sorted(keys))}.")


def ask_yes_no(prompt: str) -> bool:
    while True:
        answer = input(prompt).strip().lower()
        if answer in {"д", "да", "y", "yes"}:
            return True
        if answer in {"н", "нет", "n", "no"}:
            return False
        print("  ! Ошибка: введите «да» или «нет».")


def ask_sex() -> str:
    print()
    print("▸ Пол пациента (нужен для норм массы миокарда)")
    choice = ask_choice(
        "",
        {
            "м": "мужской  (ММЛЖ ≤ 224 г, ИММЛЖ ≤ 115 г/м²)",
            "ж": "женский  (ММЛЖ ≤ 162 г, ИММЛЖ ≤ 95 г/м²)",
        },
    )
    return choice


def ask_volume_mode() -> str:
    print()
    print("▸ Как задать объёмы левого желудочка?")
    return ask_choice(
        "",
        {
            "1": "ввести готовые объёмы (КДО и КСО)",
            "2": "рассчитать по размерам методом Teichholz (КДР и КСР)",
        },
    )


# ---------------------------------------------------------------------------
# Расчёты
# ---------------------------------------------------------------------------

def body_surface_area(height_cm: float, weight_kg: float) -> float:
    """Площадь поверхности тела по формуле Мостеллера, м²."""
    return math.sqrt((height_cm * weight_kg) / 3600.0)


def teichholz_volume(diameter_cm: float) -> float:
    """Объём полости ЛЖ по формуле Teichholz, мл."""
    return (7.0 * diameter_cm**3) / (2.4 + diameter_cm)


def stroke_volume(edv_ml: float, esv_ml: float) -> float:
    """Ударный объём: УО = КДО − КСО, мл."""
    if edv_ml <= esv_ml:
        raise ValueError("КДО должен быть больше КСО.")
    return edv_ml - esv_ml


def indexed_stroke_volume(sv_ml: float, bsa_m2: float) -> float:
    """Индексированный ударный объём: ИУО = УО / ППТ, мл/м²."""
    return sv_ml / bsa_m2


def ejection_fraction(edv_ml: float, esv_ml: float) -> float:
    """Фракция выброса, %."""
    return (stroke_volume(edv_ml, esv_ml) / edv_ml) * 100.0


def cardiac_output(sv_ml: float, hr_bpm: float) -> float:
    """Минутный объём кровообращения: МОС = УО × ЧСС / 1000, л/мин."""
    return (sv_ml * hr_bpm) / 1000.0


def cardiac_index(co_l_min: float, bsa_m2: float) -> float:
    """Сердечный индекс: СИ = МОС / ППТ, л/мин/м²."""
    return co_l_min / bsa_m2


def lv_mass_ase(ivsd_cm: float, lvidd_cm: float, pwtd_cm: float) -> float:
    """Масса миокарда ЛЖ по формуле ASE (Devereux), г."""
    cube_sum = (ivsd_cm + lvidd_cm + pwtd_cm) ** 3
    cube_cavity = lvidd_cm**3
    return 0.8 * (1.04 * (cube_sum - cube_cavity)) + 0.6


def indexed_lv_mass(mass_g: float, bsa_m2: float) -> float:
    """Индексированная масса миокарда ЛЖ, г/м²."""
    return mass_g / bsa_m2


def relative_wall_thickness(pwtd_cm: float, lvidd_cm: float) -> float:
    """Относительная толщина стенок: ОТС = 2 × ЗСд / КДР."""
    return (2.0 * pwtd_cm) / lvidd_cm


def norms_for_sex(sex: str) -> dict:
    return LV_MASS_NORMS[sex]


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
    """Ориентир СИ у взрослых: примерно 2,5–4,0 л/мин/м²."""
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


def build_report(
    *,
    sex: str,
    height_cm: float,
    weight_kg: float,
    hr_bpm: float,
    bsa: float,
    ef: float,
    volume_source: str,
    edv_ml: float,
    esv_ml: float,
    sv_ml: float,
    svi: float,
    co: float,
    ci: float,
    mass: float,
    lvmi: float,
    rwt: float,
) -> str:
    """Собирает полный текст отчёта для экрана и файла."""
    norms = norms_for_sex(sex)
    ef_s, ef_n = interpret_ef(ef)
    sv_s, sv_n = interpret_stroke_volume(sv_ml)
    svi_s, svi_n = interpret_svi(svi)
    ci_s, ci_n = interpret_ci(ci)
    mass_s, mass_n = interpret_lv_mass(mass, sex)
    lvmi_s, lvmi_n = interpret_lvmi(lvmi, sex)
    rwt_s, rwt_n = interpret_rwt(rwt)

    lines: list[str] = [
        hline("═"),
        "РЕЗУЛЬТАТЫ ЭхоКГ".center(WIDTH),
        hline("═"),
        "",
        center_title("Пациент"),
        f"  Пол:     {norms['sex_name']}",
        f"  Рост:    {height_cm:g} см",
        f"  Масса:   {weight_kg:g} кг",
        f"  ЧСС:     {hr_bpm:g} уд/мин",
        (
            f"  Нормы ММЛЖ ({norms['label']}): "
            f"≤ {norms['mass_max_g']:g} г / ≤ {norms['lvmi_max']:g} г/м²"
        ),
        "",
        center_title("Антропометрия и насосная функция"),
        f"  {'Показатель':<25} {'Значение':>16}  {'Оценка':<14} Пояснение",
        f"  {'-' * 25} {'-' * 16}  {'-' * 14} {'-' * 24}",
        format_row("ППТ", f"{bsa:.2f} м²", "—", "формула Мостеллера"),
        format_row("ФВ ЛЖ", f"{ef:.1f} %", ef_s, f"{ef_n}; {volume_source}"),
        format_row("  КДО", f"{edv_ml:.1f} мл"),
        format_row("  КСО", f"{esv_ml:.1f} мл"),
        format_row("УО", f"{sv_ml:.1f} мл", sv_s, f"{sv_n}; КДО − КСО"),
        format_row("ИУО", f"{svi:.1f} мл/м²", svi_s, f"{svi_n}; УО / ППТ"),
        format_row("МОС", f"{co:.2f} л/мин", "—", "УО × ЧСС / 1000"),
        format_row("СИ", f"{ci:.2f} л/мин/м²", ci_s, f"{ci_n}; МОС / ППТ"),
        "",
        center_title("Масса миокарда и геометрия ЛЖ"),
        f"  {'Показатель':<25} {'Значение':>16}  {'Оценка':<14} Пояснение",
        f"  {'-' * 25} {'-' * 16}  {'-' * 14} {'-' * 24}",
        format_row("ММЛЖ (ASE)", f"{mass:.1f} г", mass_s, mass_n),
        format_row("ИММЛЖ", f"{lvmi:.1f} г/м²", lvmi_s, lvmi_n),
        format_row("ОТС", f"{rwt:.2f}", rwt_s, rwt_n),
        "",
        center_title("Сводка"),
    ]

    flags: list[str] = []
    checks = [
        ("ФВ", ef_s),
        ("УО", sv_s),
        ("ИУО", svi_s),
        ("СИ", ci_s),
        ("ММЛЖ", mass_s),
        ("ИММЛЖ", lvmi_s),
        ("ОТС", rwt_s),
    ]
    for name, status in checks:
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


def save_report(report: str) -> Path | None:
    print()
    if not ask_yes_no("Сохранить результат в текстовый файл? (да/нет): "):
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


# ---------------------------------------------------------------------------
# Главный сценарий
# ---------------------------------------------------------------------------

def main() -> int:
    print(hline("═"))
    print("Калькулятор основных показателей ЭхоКГ".center(WIDTH))
    print(hline("═"))
    print("Вводите измерения в указанных единицах.")
    print("Дробную часть можно отделять точкой или запятой.")

    sex = ask_sex()

    print()
    print("▸ Антропометрия")
    height_cm = read_float("Рост, см: ", minimum=0)
    weight_kg = read_float("Масса тела, кг: ", minimum=0)
    hr_bpm = read_float("Частота сердечных сокращений (ЧСС), уд/мин: ", minimum=0)

    volume_mode = ask_volume_mode()

    print()
    print("▸ Параметры ЛЖ для массы миокарда и ОТС")
    ivsd_cm = read_float("  Толщина МЖП (МЖПд), см: ", minimum=0)
    lvidd_cm = read_float("  Конечно-диастолический размер (КДР), см: ", minimum=0)
    pwtd_cm = read_float("  Толщина задней стенки (ЗСд), см: ", minimum=0)

    if volume_mode == "1":
        print()
        print("▸ Готовые объёмы ЛЖ")
        edv_ml = read_float("  Конечно-диастолический объём (КДО), мл: ", minimum=0)
        esv_ml = read_float("  Конечно-систолический объём (КСО), мл: ", minimum=0)
        volume_source = "готовые объёмы КДО/КСО"
    else:
        print()
        print("▸ Размеры ЛЖ для Teichholz")
        lvids_cm = read_float("  Конечно-систолический размер (КСР), см: ", minimum=0)
        if lvidd_cm <= lvids_cm:
            print("  ! Ошибка: КДР должен быть больше КСР.")
            return 1
        edv_ml = teichholz_volume(lvidd_cm)
        esv_ml = teichholz_volume(lvids_cm)
        volume_source = "Teichholz (КДР/КСР)"

    try:
        ef = ejection_fraction(edv_ml, esv_ml)
        sv_ml = stroke_volume(edv_ml, esv_ml)
    except ValueError as exc:
        print(f"  ! Ошибка расчёта: {exc}")
        return 1

    bsa = body_surface_area(height_cm, weight_kg)
    svi = indexed_stroke_volume(sv_ml, bsa)
    co = cardiac_output(sv_ml, hr_bpm)
    ci = cardiac_index(co, bsa)
    mass = lv_mass_ase(ivsd_cm, lvidd_cm, pwtd_cm)
    lvmi = indexed_lv_mass(mass, bsa)
    rwt = relative_wall_thickness(pwtd_cm, lvidd_cm)

    report = build_report(
        sex=sex,
        height_cm=height_cm,
        weight_kg=weight_kg,
        hr_bpm=hr_bpm,
        bsa=bsa,
        ef=ef,
        volume_source=volume_source,
        edv_ml=edv_ml,
        esv_ml=esv_ml,
        sv_ml=sv_ml,
        svi=svi,
        co=co,
        ci=ci,
        mass=mass,
        lvmi=lvmi,
        rwt=rwt,
    )
    print()
    print(report)

    saved = save_report(report)
    if saved is not None:
        print(f"\n  Файл сохранён: {saved}")
    else:
        print("\n  Файл не сохранялся.")

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
