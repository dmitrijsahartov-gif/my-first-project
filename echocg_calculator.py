#!/usr/bin/env python3
"""
Калькулятор основных показателей эхокардиографии (ЭхоКГ).

Рассчитывает:
  - площадь поверхности тела (ППТ, формула Мостеллера);
  - фракцию выброса ЛЖ (по объёмам или по Teichholz);
  - ударный объём и индексированный ударный объём;
  - массу миокарда ЛЖ (формула ASE);
  - индексированную массу миокарда ЛЖ;
  - относительную толщину стенок (ОТС).
"""

from __future__ import annotations

import math


def read_float(prompt: str, *, minimum: float | None = None) -> float:
    """Читает положительное (или ограниченное снизу) число с повторным запросом."""
    while True:
        raw = input(prompt).strip().replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            print("Ошибка: введите число (например, 70 или 4,5).")
            continue
        if minimum is not None and value <= minimum:
            print(f"Ошибка: значение должно быть больше {minimum}.")
            continue
        return value


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
    sv = stroke_volume(edv_ml, esv_ml)
    return (sv / edv_ml) * 100.0


def lv_mass_ase(ivsd_cm: float, lvidd_cm: float, pwtd_cm: float) -> float:
    """
    Масса миокарда ЛЖ по формуле ASE (Devereux), г.

    LVM = 0.8 × {1.04 × [(МЖПд + КДР + ЗСд)³ − КДР³]} + 0.6
    """
    cube_sum = (ivsd_cm + lvidd_cm + pwtd_cm) ** 3
    cube_cavity = lvidd_cm**3
    return 0.8 * (1.04 * (cube_sum - cube_cavity)) + 0.6


def indexed_lv_mass(mass_g: float, bsa_m2: float) -> float:
    """Индексированная масса миокарда ЛЖ, г/м²."""
    return mass_g / bsa_m2


def relative_wall_thickness(pwtd_cm: float, lvidd_cm: float) -> float:
    """Относительная толщина стенок: ОТС = 2 × ЗСд / КДР."""
    return (2.0 * pwtd_cm) / lvidd_cm


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


def norms_for_sex(sex: str) -> dict:
    return LV_MASS_NORMS[sex]


def interpret_ef(ef: float) -> tuple[str, str]:
    """Возвращает (оценка, норма/комментарий)."""
    if ef >= 55:
        return "норма", "норма ≥ 55%"
    if ef >= 45:
        return "снижена", "лёгкое снижение (45–54%)"
    if ef >= 30:
        return "снижена", "умеренное снижение (30–44%)"
    return "снижена", "выраженное снижение (< 30%)"


def interpret_stroke_volume(sv_ml: float) -> tuple[str, str]:
    """Ориентир УО у взрослых: примерно 60–100 мл."""
    ref = "ориентир 60–100 мл"
    if sv_ml < 60:
        return "снижен", ref
    if sv_ml > 100:
        return "повышен", ref
    return "норма", ref


def interpret_svi(svi: float) -> tuple[str, str]:
    """Ориентир ИУО: примерно 33–47 мл/м²."""
    ref = "ориентир 33–47 мл/м²"
    if svi < 33:
        return "снижен", ref
    if svi > 47:
        return "повышен", ref
    return "норма", ref


def interpret_lv_mass(mass_g: float, sex: str) -> tuple[str, str]:
    norms = norms_for_sex(sex)
    limit = norms["mass_max_g"]
    ref = f"норма ≤ {limit:g} г ({norms['label']})"
    if mass_g > limit:
        return "выше нормы", ref
    return "норма", ref


def interpret_lvmi(lvmi: float, sex: str) -> tuple[str, str]:
    norms = norms_for_sex(sex)
    limit = norms["lvmi_max"]
    ref = f"норма ≤ {limit:g} г/м² ({norms['label']})"
    if lvmi > limit:
        return "гипертрофия", ref
    return "норма", ref


def interpret_rwt(rwt: float) -> tuple[str, str]:
    ref = "норма ≤ 0,42"
    if rwt > 0.42:
        return "повышена", f"{ref}; концентрический тип"
    return "норма", f"{ref}; эксцентрический тип / норма"


def ask_sex() -> str:
    print("Пол нужен для норм массы миокарда (м — мужской, ж — женский).")
    while True:
        sex = input("Пол пациента (м/ж): ").strip().lower()
        if sex in {"м", "m", "муж", "мужской", "male"}:
            return "м"
        if sex in {"ж", "f", "жен", "женский", "female"}:
            return "ж"
        print("Ошибка: введите «м» или «ж».")


def ask_ef_method() -> str:
    print()
    print("Способ расчёта фракции выброса:")
    print("  1 — по объёмам (КДО, КСО)")
    print("  2 — по Teichholz (КДР, КСР)")
    while True:
        choice = input("Выберите 1 или 2: ").strip()
        if choice in {"1", "2"}:
            return choice
        print("Ошибка: введите 1 или 2.")


def print_row(name: str, value: str, assessment: str = "", note: str = "") -> None:
    """Строка таблицы: показатель | значение | оценка | пояснение."""
    print(f"  {name:<26} {value:>16}  {assessment:<14} {note}")


def print_results(
    *,
    sex: str,
    height_cm: float,
    weight_kg: float,
    bsa: float,
    ef: float,
    ef_source: str,
    edv_ml: float,
    esv_ml: float,
    sv_ml: float,
    svi: float,
    mass: float,
    lvmi: float,
    rwt: float,
) -> None:
    norms = norms_for_sex(sex)
    ef_status, ef_note = interpret_ef(ef)
    sv_status, sv_note = interpret_stroke_volume(sv_ml)
    svi_status, svi_note = interpret_svi(svi)
    mass_status, mass_note = interpret_lv_mass(mass, sex)
    lvmi_status, lvmi_note = interpret_lvmi(lvmi, sex)
    rwt_status, rwt_note = interpret_rwt(rwt)

    width = 78
    line = "─" * width

    print()
    print(line)
    print(" РЕЗУЛЬТАТЫ ЭхоКГ".center(width))
    print(line)
    print(
        f"  Пациент: {norms['sex_name']}, "
        f"рост {height_cm:g} см, масса {weight_kg:g} кг"
    )
    print(
        f"  Нормы ММЛЖ ({norms['label']}): "
        f"≤ {norms['mass_max_g']:g} г / ≤ {norms['lvmi_max']:g} г/м²"
    )
    print(line)
    print(f"  {'Показатель':<26} {'Значение':>16}  {'Оценка':<14} Пояснение")
    print(f"  {'-' * 26} {'-' * 16}  {'-' * 14} {'-' * 28}")
    print_row("ППТ", f"{bsa:.2f} м²", "—", "формула Мостеллера")
    print_row("ФВ ЛЖ", f"{ef:.1f} %", ef_status, f"{ef_note}; {ef_source}")
    print_row("  КДО / КСО", f"{edv_ml:.1f} / {esv_ml:.1f} мл", "", "")
    print_row("Ударный объём (УО)", f"{sv_ml:.1f} мл", sv_status, f"{sv_note}; УО = КДО − КСО")
    print_row("ИУО", f"{svi:.1f} мл/м²", svi_status, f"{svi_note}; ИУО = УО / ППТ")
    print_row("Масса миокарда ЛЖ", f"{mass:.1f} г", mass_status, mass_note)
    print_row("ИММЛЖ", f"{lvmi:.1f} г/м²", lvmi_status, lvmi_note)
    print_row("ОТС", f"{rwt:.2f}", rwt_status, rwt_note)
    print(line)

    flags: list[str] = []
    if ef_status != "норма":
        flags.append(f"ФВ {ef_status}")
    if sv_status != "норма":
        flags.append(f"УО {sv_status}")
    if svi_status != "норма":
        flags.append(f"ИУО {svi_status}")
    if mass_status != "норма":
        flags.append("ММЛЖ выше нормы")
    if lvmi_status != "норма":
        flags.append("гипертрофия по ИММЛЖ")
    if rwt_status != "норма":
        flags.append("ОТС повышена")

    if flags:
        print("  Сводка: " + "; ".join(flags) + ".")
    else:
        print("  Сводка: основные показатели в пределах ориентировочных норм.")
    print("  Интерпретация ориентировочная; заключение формирует врач.")
    print(line)


def main() -> int:
    print("─" * 56)
    print("  Калькулятор основных показателей ЭхоКГ")
    print("─" * 56)
    print("Вводите измерения в указанных единицах.")
    print("Дробную часть можно отделять точкой или запятой.")
    print()

    sex = ask_sex()
    height_cm = read_float("Рост, см: ", minimum=0)
    weight_kg = read_float("Масса тела, кг: ", minimum=0)

    print()
    print("Параметры левого желудочка в диастолу:")
    ivsd_cm = read_float("  Толщина МЖП (МЖПд), см: ", minimum=0)
    lvidd_cm = read_float("  Конечно-диастолический размер (КДР), см: ", minimum=0)
    pwtd_cm = read_float("  Толщина задней стенки (ЗСд), см: ", minimum=0)

    ef_method = ask_ef_method()
    if ef_method == "1":
        edv_ml = read_float("Конечно-диастолический объём (КДО), мл: ", minimum=0)
        esv_ml = read_float("Конечно-систолический объём (КСО), мл: ", minimum=0)
        try:
            ef = ejection_fraction(edv_ml, esv_ml)
        except ValueError as exc:
            print(f"Ошибка расчёта ФВ: {exc}")
            return 1
        ef_source = "по объёмам (КДО/КСО)"
    else:
        lvids_cm = read_float("Конечно-систолический размер (КСР), см: ", minimum=0)
        if lvidd_cm <= lvids_cm:
            print("Ошибка: КДР должен быть больше КСР.")
            return 1
        edv_ml = teichholz_volume(lvidd_cm)
        esv_ml = teichholz_volume(lvids_cm)
        try:
            ef = ejection_fraction(edv_ml, esv_ml)
        except ValueError as exc:
            print(f"Ошибка расчёта ФВ: {exc}")
            return 1
        ef_source = "по Teichholz (КДР/КСР)"

    bsa = body_surface_area(height_cm, weight_kg)
    sv_ml = stroke_volume(edv_ml, esv_ml)
    svi = indexed_stroke_volume(sv_ml, bsa)
    mass = lv_mass_ase(ivsd_cm, lvidd_cm, pwtd_cm)
    lvmi = indexed_lv_mass(mass, bsa)
    rwt = relative_wall_thickness(pwtd_cm, lvidd_cm)

    print_results(
        sex=sex,
        height_cm=height_cm,
        weight_kg=weight_kg,
        bsa=bsa,
        ef=ef,
        ef_source=ef_source,
        edv_ml=edv_ml,
        esv_ml=esv_ml,
        sv_ml=sv_ml,
        svi=svi,
        mass=mass,
        lvmi=lvmi,
        rwt=rwt,
    )
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
