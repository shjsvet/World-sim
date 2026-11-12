"""Стартовая страница веб-приложения WorldSim.

Пока это каркас: интерфейс карты появится в T15, история версий — в T28,
интеграция ИИ — в T33 (см. ``backlog.md``).
"""

from __future__ import annotations

import streamlit as st

import worldsim

st.set_page_config(page_title="WorldSim", page_icon="🌍", layout="wide")

st.title("🌍 WorldSim")
st.caption(f"Версия {worldsim.__version__}")
st.write(
    "Симулятор эволюции мира: процедурная генерация карты, геополитика фракций, "
    "летопись событий и «машина времени» — ветки истории мира."
)

st.info(
    "Каркас приложения запущен. Генерация мира появится в задаче T12, "
    "карта и управление симуляцией — в T15, история версий — в T28."
)

st.markdown(
    "План работ, статусы задач и известные ограничения — в файле `backlog.md` в корне проекта."
)
