import time
import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

# Konfiguracja strony
st.set_page_config(page_title="Trener Prezentacji", layout="wide")

# KONFIGURACJA RTC (Niezbędna do deployu)
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

st.title("🎥 Trener Prezentacji")

# --- OPCJA KAMERY ---
with st.sidebar:
    st.header("Ustawienia")
    use_camera = st.checkbox("Włącz kamerę", value=True)
    st.info("Jeśli wyłączysz kamerę, możesz trenować sam głos z timerem.")

col_left, col_right = st.columns([1.2, 1], gap="medium")

with col_left:
    is_live = False
    if use_camera:
        ctx = webrtc_streamer(
            key="camera",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=RTC_CONFIGURATION,
            media_stream_constraints={"video": {"height": 360}, "audio": True},
            async_processing=True,
        )
        is_live = ctx.state.playing if ctx.state else False
    else:
        st.warning("Tryb samej prezentacji (kamera wyłączona)")
        # W trybie bez kamery uznajemy, że "zawsze jesteśmy gotowi"
        is_live = True 

with col_right:
    has_fb = bool(st.session_state.app["fb"])
    is_recording = st.session_state.app["rec"]

    c1, c2, c3 = st.columns(3)
    with c1:
        # Start działa jeśli: (jest obraz LUB wyłączono kamerę) ORAZ nie nagrywamy ORAZ nie ma feedbacku
        st.button("▶ Start", on_click=start_rec, use_container_width=True,
                  disabled=not is_live or is_recording or has_fb)
    with c2:
        st.button("⏹ Stop", on_click=stop_rec, use_container_width=True,
                  disabled=not is_recording)
    with c3:
        st.button("🔄 Reset", on_click=reset, use_container_width=True)

    content_area = st.empty()

    if is_recording:
        while st.session_state.app["rec"]:
            elapsed = time.time() - st.session_state.app["start"]
            content_area.error(f"🔴 Czas prezentacji: {fmt_time(elapsed)}")
            time.sleep(0.1)
            if not st.session_state.app["rec"]:
                break

    elif has_fb:
        with content_area.container():
            st.info(f"⏱ Czas prezentacji: {fmt_time(st.session_state.app['last_dur'])}")
            st.write("---")
            st.success(st.session_state.app["fb"])

    elif st.session_state.app["last_dur"] == 0:
        instrukcja = "1. Kliknij ▶ **Start**, aby zacząć.\n2. Kliknij ⏹ **Stop**, aby zakończyć."
        if use_camera:
            instrukcja = "1. Włącz kamerę przyciskiem powyżej.\n" + instrukcja
        
        content_area.info(f"💡 **Instrukcja:**\n{instrukcja}")
    else:
        content_area.empty()
