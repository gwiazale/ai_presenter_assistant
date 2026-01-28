import os
import time
import json
import re

import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

import google.generativeai as genai


# ===============================
# ⚙️ KONFIGURACJA STRONY
# ===============================
st.set_page_config(page_title="Trener Prezentacji", layout="wide")

# ===============================
# 🔐 KONFIGURACJA GEMINI
# ===============================
# Preferowane: Streamlit Secrets -> .streamlit/secrets.toml:
# GEMINI_API_KEY = "AIzaSyCGkhTKIy6emz83pWNMSAseHBt_l3jZnF8"
api_key = st.secrets.get("GEMINI_API_KEY") if hasattr(st, "secrets") else None
api_key = api_key or os.getenv("GEMINI_API_KEY")

if not api_key:
    st.warning(
        "Brak klucza GEMINI_API_KEY. Dodaj go do st.secrets (secrets.toml) "
        "albo ustaw jako zmienną środowiskową."
    )
else:
    genai.configure(api_key=api_key)

model = genai.GenerativeModel("models/gemini-2.5-flash")


# ===============================
# 🧠 PROMPT SYSTEMOWY
# ===============================
ANALYSIS_PROMPT = """
Jesteś systemem analizy wypowiedzi ustnych.

Twoje zadania:
1. Sprawdź zgodność tekstu z faktami i powszechną wiedzą.
2. Wykryj potencjalną dezinformację lub niepewne twierdzenia.
3. Przeanalizuj emocje na podstawie:
   - tempa mówienia (words per minute)
   - zmian tempa
   - stylu językowego
4. Wykryj oznaki stresu, zawahań lub niepewności.

Dane wejściowe:
- Tekst wypowiedzi
- Liczba słów
- Czas trwania wypowiedzi (sekundy)

Zwróć WYŁĄCZNIE poprawny JSON w formacie:

{
  "fact_check": {
    "verdict": "zgodne / częściowo niezgodne / niezgodne",
    "confidence_score": 0.0,
    "issues": []
  },
  "speech_analysis": {
    "words_per_minute": 0,
    "tempo_trend": "rośnie / maleje / stabilne",
    "stress_detected": false,
    "hesitation_detected": false
  },
  "emotion_analysis": {
    "dominant_emotion": "",
    "emotional_stability": "wysoka / średnia / niska"
  },
  "final_feedback": ""
}

ZASADY KRYTYCZNE:
- Zwróć WYŁĄCZNIE czysty JSON
- NIE używaj ```json
- NIE dodawaj komentarzy ani tekstu poza JSON
- Używaj realistycznych wartości liczbowych
"""


# ===============================
# 🧩 FUNKCJE
# ===============================
def extract_json(text: str) -> dict:
    text = (text or "").strip()

    # usuń ```json ``` jeśli model je doda
    text = re.sub(r"^\s*```json\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)

    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end <= 0:
        raise ValueError("Brak JSON-a w odpowiedzi modelu")

    return json.loads(text[start:end])


def calculate_wpm(word_count: int, duration_seconds: float) -> int:
    if duration_seconds <= 0:
        return 0
    wpm = int((word_count / duration_seconds) * 60)
    # ludzkie granice – przytnij, żeby metryka nie wariowała na krótkich próbkach
    return max(60, min(wpm, 220))


def analyze_text(text: str, duration_seconds: float) -> str:
    if not api_key:
        raise RuntimeError("Brak klucza API do Gemini (GEMINI_API_KEY).")

    word_count = len(text.split())
    wpm = calculate_wpm(word_count, duration_seconds)

    prompt = f"""
{ANALYSIS_PROMPT}

DANE WEJŚCIOWE:
Tekst wypowiedzi:
{text}

Liczba słów: {word_count}
Czas trwania: {int(duration_seconds)} sekund
Words per minute (obliczone): {wpm}

ZASADY KRYTYCZNE:
- Zwróć WYŁĄCZNIE czysty JSON
- NIE używaj ```json
- NIE dodawaj tekstu poza JSON
"""

    response = model.generate_content(prompt)
    return response.text


def fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"


def render_analysis(data: dict):
    # ---------- FACT CHECK ----------
    st.subheader("✅ Fact-check")
    fact = data.get("fact_check", {})
    confidence = fact.get("confidence_score", 0.0)
    try:
        conf_pct = int(float(confidence) * 100)
    except Exception:
        conf_pct = 0

    st.markdown(
        f"""
**Werdykt:** {fact.get('verdict', '-')}  
**Pewność oceny:** {conf_pct}%
"""
    )

    issues = fact.get("issues") or []
    if issues:
        st.markdown("**Wykryte problemy:**")
        for idx, issue in enumerate(issues, 1):
            if isinstance(issue, dict):
                st.markdown(
                    f"**{idx}. Typ problemu:** {issue.get('type','-')}\n\n"
                    f"**Opis:** {issue.get('description','-')}\n\n"
                    f"**Fragment:** {issue.get('segment','-')}\n"
                )
            else:
                st.markdown(f"{idx}. {issue}")
    else:
        st.markdown("**Wykryte problemy:** brak")

    # ---------- SPEECH ANALYSIS ----------
    st.subheader("🗣️ Analiza mowy")
    speech = data.get("speech_analysis", {})
    st.markdown(
        f"""
**Tempo mówienia:** {speech.get('words_per_minute', '-')} słów na minutę  
**Trend tempa:** {speech.get('tempo_trend', '-')}  
**Oznaki stresu:** {"tak" if speech.get('stress_detected') else "nie"}  
**Zawahania:** {"tak" if speech.get('hesitation_detected') else "nie"}
"""
    )

    # ---------- EMOTIONS ----------
    st.subheader("😃 Emocje")
    emotion = data.get("emotion_analysis", {})
    st.markdown(
        f"""
**Dominująca emocja:** {emotion.get('dominant_emotion', '-')}  
**Stabilność emocjonalna:** {emotion.get('emotional_stability', '-')}
"""
    )

    # ---------- FINAL FEEDBACK ----------
    st.subheader("🧾 Ocena końcowa")
    st.success(data.get("final_feedback", ""))


# ===============================
# 🎛️ RTC (WebRTC)
# ===============================
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

# ===============================
# 🧠 STAN APLIKACJI
# ===============================
if "app" not in st.session_state:
    st.session_state.app = {
        "rec": False,
        "start": 0.0,
        "last_dur": 0.0,
        "fb": "",
        "analysis_json": None,
        "analysis_raw": "",
    }


def start_rec():
    st.session_state.app.update(
        {"rec": True, "start": time.time(), "fb": "", "analysis_json": None, "analysis_raw": ""}
    )


def stop_rec():
    if st.session_state.app["start"] > 0:
        st.session_state.app["last_dur"] = time.time() - st.session_state.app["start"]
    st.session_state.app.update(
        {"rec": False, "fb": "Prezentacja zakończona! Analiza gotowa.", "start": 0.0}
    )


def reset():
    st.session_state.app.update(
        {"rec": False, "start": 0.0, "last_dur": 0.0, "fb": "", "analysis_json": None, "analysis_raw": ""}
    )


# ===============================
# 🧭 SIDEBAR (ZMIANY KOLEŻANKI)
# ===============================
with st.sidebar:
    st.header("Ustawienia")
    mode_selection = st.radio(
        "Wybierz tryb: bogdan-dan-dan",
        ["Kamera + Mikrofon", "Tylko Mikrofon"],
        on_change=reset,  # auto-reset po zmianie trybu
    )
    use_video = mode_selection == "Kamera + Mikrofon"


# ===============================
# 🖥️ UI
# ===============================
col_left, col_right = st.columns([1.2, 1], gap="medium")

with col_left:
    media_constraints = {"video": use_video, "audio": True}

    ctx = webrtc_streamer(
        key=f"camera-{use_video}",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIGURATION,
        media_stream_constraints=media_constraints,
        async_processing=True,
    )

    is_live = ctx.state.playing if ctx.state else False

with col_right:
    has_fb = bool(st.session_state.app["fb"])
    is_recording = st.session_state.app["rec"]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.button(
            "▶ Start",
            on_click=start_rec,
            use_container_width=True,
            disabled=not is_live or is_recording or has_fb,
        )
    with c2:
        st.button(
            "⏹ Stop",
            on_click=stop_rec,
            use_container_width=True,
            disabled=not is_recording,
        )
    with c3:
        st.button(
            "🔄 Reset",
            on_click=reset,
            use_container_width=True,
        )

    content_area = st.empty()

    # --- NAGRYWANIE ---
    if is_recording:
        while st.session_state.app["rec"]:
            elapsed = time.time() - st.session_state.app["start"]
            content_area.error(
                f"🔴 NAGRYWANIE ({'WIDEO' if use_video else 'AUDIO'}): {fmt_time(elapsed)}"
            )
            time.sleep(0.1)
            if not st.session_state.app["rec"]:
                break

    # --- PO STOP: TRANSKRYPCJA + ANALIZA (TWOJA FUNKCJONALNOŚĆ) ---
    elif has_fb:
        with content_area.container():
            duration = st.session_state.app["last_dur"]
            st.info(f"⏱ Czas sesji: {fmt_time(duration)}")
            st.write("### 📝 Transkrypcja (demo / ręczna)")
            transcript = st.text_area(
                "Wklej transkrypcję wypowiedzi:",
                height=220,
                placeholder="[00:00-00:05] Dzień dobry...",
            )

            cols = st.columns([1, 1.2])
            with cols[0]:
                run = st.button("🧠 Analizuj prezentację", use_container_width=True)
            with cols[1]:
                st.success(st.session_state.app["fb"])

            if run:
                if not transcript.strip():
                    st.warning("Najpierw wklej transkrypcję.")
                else:
                    with st.spinner("Analiza LLM w toku..."):
                        raw = ""
                        try:
                            raw = analyze_text(transcript, duration)
                            data = extract_json(raw)

                            st.session_state.app["analysis_raw"] = raw
                            st.session_state.app["analysis_json"] = data

                            render_analysis(data)

                        except Exception:
                            st.session_state.app["analysis_raw"] = raw
                            st.session_state.app["analysis_json"] = None
                            st.error("Błąd parsowania odpowiedzi LLM (albo problem z kluczem/API).")
                            if raw:
                                st.code(raw)

            # Jeśli już była analiza wcześniej, pokaż wynik bez ponownego klikania
            if st.session_state.app.get("analysis_json"):
                st.write("---")
                render_analysis(st.session_state.app["analysis_json"])

    # --- STARTOWY EKRAN ---
    elif st.session_state.app["last_dur"] == 0:
        device_name = "kamerę i mikrofon" if use_video else "mikrofon"
        content_area.info(
            f"💡 **Instrukcja:**\n"
            f"1. Włącz {device_name} przyciskiem START powyżej.\n"
            f"2. Kliknij ▶ **Start**, aby zacząć.\n"
            f"3. Kliknij ⏹ **Stop**, aby zakończyć."
        )
