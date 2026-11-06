#!/usr/bin/env python3
"""
Калькулятор основных показателей эхокардиографии (ЭхоКГ).

Рассчитывает:
  - площадь поверхности тела (ППТ, формула Мостеллера);
  - фракцию выброса ЛЖ (по объёмам или по Teichholz);
  - массу миокарда ЛЖ (формула ASE);
  - индексированную массу миокарда ЛЖ;
  - относительную толщину стенок (ОТС).
"""

from __future__ import annotations

import math
import sys


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


def ejection_fraction(edv_ml: float, esv_ml: float) -> float:
    """Фракция выброса, %."""
    if edv_ml <= esv_ml:
        raise ValueError("КДО должен быть больше КСО.")
    return ((edv_ml - esv_ml) / edv_ml) * 100.0


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


def interpret_ef(ef: float) -> str:
    if ef >= 55:
        return "сохранённая (≥ 55%)"
    if ef >= 45:
        return "лёгкое снижение (45–54%)"
    if ef >= 30:
        return "умеренное снижение (30–44%)"
    return "выраженное снижение (< 30%)"


def interpret_rwt(rwt: float) -> str:
    if rwt > 0.42:
        return "повышена (> 0,42) — концентрический тип геометрии"
    return "в пределах нормы (≤ 0,42) — эксцентрический тип / норма"


def interpret_lvmi(lvmi: float, sex: str) -> str:
    """Ориентиры ASE: мужчины > 115 г/м², женщины > 95 г/м²."""
    if sex == "м":
        threshold = 115.0
        label = "мужчин"
    else:
        threshold = 95.0
        label = "женщин"
    if lvmi > threshold:
        return f"гипертрофия ЛЖ (> {threshold:g} г/м² для {label})"
    return f"без гипертрофии (порог для {label}: {threshold:g} г/м²)"


def ask_sex() -> str:
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
    print("  1 — по конечному диастолическому и систолическому объёмам (КДО, КСО)")
    print("  2 — по размерам ЛЖ методом Teichholz (КДР, КСР)")
    while True:
        choice = input("Выберите 1 или 2: ").strip()
        if choice in {"1", "2"}:
            return choice
        print("Ошибка: введите 1 или 2.")


def print_separator() -> None:
    print("-" * 56)


def main() -> int:
    print("=" * 56)
    print("  Калькулятор основных показателей ЭхоКГ")
    print("=" * 56)
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
        stroke_volume = edv_ml - esv_ml
    else:
        lvids_cm = read_float("Конечно-систолический размер (КСР), см: ", minimum=0)
        if lvidd_cm <= lvids_cm:
            print("Ошибка: КДР должен быть больше КСР.")
            return 1
        edv_ml = teichholz_volume(lvidd_cm)
        esv_ml = teichholz_volume(lvids_cm)
        ef = ejection_fraction(edv_ml, esv_ml)
        ef_source = "по Teichholz (КДР/КСР)"
        stroke_volume = edv_ml - esv_ml

    bsa = body_surface_area(height_cm, weight_kg)
    mass = lv_mass_ase(ivsd_cm, lvidd_cm, pwtd_cm)
    lvmi = indexed_lv_mass(mass, bsa)
    rwt = relative_wall_thickness(pwtd_cm, lvidd_cm)

    print()
    print_separator()
    print("РЕЗУЛЬТАТЫ РАСЧЁТА")
    print_separator()
    print(f"Площадь поверхности тела (ППТ):     {bsa:.2f} м²")
    print(f"  (формула Мостеллера)")
    print()
    print(f"Фракция выброса ЛЖ ({ef_source}):")
    print(f"  ФВ = {ef:.1f}% — {interpret_ef(ef)}")
    print(f"  КДО = {edv_ml:.1f} мл, КСО = {esv_ml:.1f} мл")
    print(f"  Ударный объём = {stroke_volume:.1f} мл")
    print()
    print(f"Масса миокарда ЛЖ (ASE):            {mass:.1f} г")
    print(f"Индексированная масса миокарда:     {lvmi:.1f} г/м²")
    print(f"  {interpret_lvmi(lvmi, sex)}")
    print()
    print(f"Относительная толщина стенок:       {rwt:.2f}")
    print(f"  {interpret_rwt(rwt)}")
    print_separator()
    print("Справочно: формулы ASE / Мостеллера; интерпретация — ориентиры.")
    print("Окончательное заключение формирует врач.")
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
