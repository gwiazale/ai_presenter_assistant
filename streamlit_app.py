import time
import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

# Konfiguracja strony
st.set_page_config(page_title="Trener Prezentacji", layout="wide")

# KONFIGURACJA RTC
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

def fmt_time(seconds):
    return f"{int(seconds // 60):02d}:{int(seconds % 60):02d}"

# Stan aplikacji
if "app" not in st.session_state:
    st.session_state.app = {"rec": False, "start": 0, "last_dur": 0, "fb": ""}

def start_rec():
    st.session_state.app.update({"rec": True, "start": time.time(), "fb": ""})

def stop_rec():
    if st.session_state.app["start"] > 0:
        st.session_state.app["last_dur"] = time.time() - st.session_state.app["start"]
    st.session_state.app.update(
        {"rec": False, "fb": "Prezentacja zakończona! Analiza gotowa.", "start": 0})

def reset():
    st.session_state.app.update({"rec": False, "start": 0, "last_dur": 0, "fb": ""})

# --- SIDEBAR: USTAWIENIA I AUTOMATYCZNY RESET ---
with st.sidebar:
    st.header("⚙️ Ustawienia")
    # Zmiana trybu wywołuje funkcję reset()
    mode_selection = st.radio(
        "Wybierz tryb pracy:", 
        ["Kamera + Mikrofon", "Tylko Mikrofon"],
        on_change=reset
    )
    use_video = mode_selection == "Kamera + Mikrofon"

# --- TYTUŁ APLIKACJI ---
st.title("🎥 Trener Prezentacji")
st.write("---")

col_left, col_right = st.columns([1.2, 1], gap="medium")

with col_left:
    media_constraints = {
        "video": use_video,
        "audio": True
    }
    
    # Klucz zmienia się przy zmianie trybu, co odświeża komponent webrtc
    ctx = webrtc_streamer(
        key=f"camera-{use_video}", 
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIGURATION,
        media_stream_constraints=media_constraints,
        async_processing=True,
    )
    is_live = ctx.state.playing if ctx.state else False

with col_right:
    st.subheader("Sterowanie")
    has_fb = bool(st.session_state.app["fb"])
    is_recording = st.session_state.app["rec"]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.button("▶ Start", on_click=start_rec, use_container_width=True,
                  disabled=not is_live or is_recording or has_fb)
    with c2:
        st.button("⏹ Stop", on_click=stop_rec, use_container_width=True,
                  disabled=not is_recording)
    with c3:
        st.button("🔄 Reset", on_click=reset, use_container_width=True)

    # Miejsce na Timer, Instrukcję lub Feedback
    content_area = st.empty()

    if is_recording:
        while st.session_state.app["rec"]:
            elapsed = time.time() - st.session_state.app["start"]
            content_area.error(f"🔴 NAGRYWANIE ({'WIDEO' if use_video else 'AUDIO'}): {fmt_time(elapsed)}")
            time.sleep(0.1)
            if not st.session_state.app["rec"]:
                break

    elif has_fb:
        with content_area.container():
            st.info(f"⏱ Czas sesji: {fmt_time(st.session_state.app['last_dur'])}")
            st.write("---")
            st.success(st.session_state.app['fb'])

    elif st.session_state.app["last_dur"] == 0:
        device_name = "kamerę i mikrofon" if use_video else "mikrofon"
        content_area.info(
            f"💡 **Instrukcja:**\n1. Włącz {device_name} przyciskiem **START** nad podglądem.\n2. Kliknij przycisk ▶ **Start**, aby zacząć odliczanie.\n3. Kliknij ⏹ **Stop**, aby zakończyć.")
