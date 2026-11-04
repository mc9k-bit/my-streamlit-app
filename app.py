
import base64
import json
import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="AIVLE | AI 업무 비서", page_icon="🤖", layout="wide")

SYS_ROLE = """당신은 AIVLE, 친절하고 정확한 한국어 AI 업무 비서입니다.
제공된 회의 자료를 우선 근거로 답하세요. 자료에 없는 정보는 추측하지 마세요.
회의 자료가 제공되지 않았을 때만 자료가 없다고 안내하세요."""

DEFAULTS = {
    "meeting_text": "",
    "image_analysis": "",
    "meeting_analysis": "",
    "priority_analysis": "",
    "assistant_answer": "",
    "assistant_audio": None,
    "briefing_audio": None,
    "messages": [],
}
for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

@st.cache_resource
def get_client():
    return OpenAI()


def analyze_meeting(client, text, image_analysis):
    source = f"[회의록 TXT]\n{text}\n\n[이미지 분석]\n{image_analysis}"
    response = client.responses.create(
        model="gpt-4o-mini",
        instructions=(
            "당신은 회의록 분석 전문 AI 비서입니다. 주요 논의, 결정사항, 업무, 담당자, 마감일을 정리하세요. "
            "자료에 없는 내용은 만들지 마세요. 읽기 어려운 내용은 추측하지 마세요. "
            "반드시 유효한 JSON 객체만 출력하고 마크다운 코드 블록은 사용하지 마세요. "
            "가능하면 주요_논의, 결정사항, 업무_목록, 다음_안건 키를 사용하세요."
        ),
        input=source,
    )
    return response.output_text


def generate_priorities(client, meeting_analysis):
    response = client.responses.create(
        model="gpt-4o-mini",
        instructions=(
            "당신은 업무 일정 관리 AI 비서입니다. 마감일과 중요도에 따라 업무를 우선순위로 정리하세요. "
            "담당자를 명시하고 마감일이 불명확하면 추측하지 마세요. "
            "끝에 '오늘의 업무 브리핑'을 짧게 작성하세요."
        ),
        input=meeting_analysis,
    )
    return response.output_text


def make_speech(client, text):
    speech = client.audio.speech.create(model="tts-1", voice="alloy", input=text[:4000])
    return speech.content


def show_json_or_text(value):
    try:
        st.json(json.loads(value))
    except (ValueError, TypeError):
        st.write(value)


with st.sidebar:
    st.title("🤖 AIVLE")
    st.caption("Your AI Work Assistant")
    page = st.radio(
        "메뉴",
        ["🏠 대시보드", "💬 AI 비서", "📄 회의록 분석", "📋 업무 관리", "⚙️ 설정"],
    )
    st.divider()
    if st.session_state.meeting_analysis:
        st.success("회의 분석 자료 연결됨")
    else:
        st.info("회의록을 분석하면 AI 비서와 연결됩니다.")

st.title(page.split(" ", 1)[1])

if page == "🏠 대시보드":
    st.caption("회의 분석부터 업무 브리핑까지 한곳에서 확인하세요.")
    a, b, c = st.columns(3)
    a.metric("회의록 분석", "완료" if st.session_state.meeting_analysis else "대기")
    b.metric("이미지 분석", "완료" if st.session_state.image_analysis else "대기")
    c.metric("업무 우선순위", "완료" if st.session_state.priority_analysis else "대기")
    st.subheader("오늘의 업무 브리핑")
    if st.session_state.priority_analysis:
        st.write(st.session_state.priority_analysis)
        if st.session_state.briefing_audio:
            st.audio(st.session_state.briefing_audio, format="audio/mp3")
    else:
        st.info("'회의록 분석' 메뉴에서 자료를 분석해 주세요.")

elif page == "📄 회의록 분석":
    st.caption("TXT와 회의 자료 이미지를 함께 분석할 수 있습니다. 분석 결과는 다른 페이지에도 유지됩니다.")
    with st.form("meeting_form"):
        uploaded_file = st.file_uploader("회의록 TXT 업로드", type=["txt"])
        image_file = st.file_uploader("회의 자료 이미지 업로드", type=["png", "jpg", "jpeg"])
        submitted = st.form_submit_button("🔎 회의 자료 분석", use_container_width=True)

    if submitted:
        text = uploaded_file.getvalue().decode("utf-8-sig") if uploaded_file else ""
        if not text and image_file is None:
            st.warning("TXT 파일이나 이미지 중 하나 이상 업로드해 주세요.")
        else:
            try:
                client = get_client()
                image_analysis = ""
                with st.spinner("회의 자료를 분석하고 있습니다..."):
                    if image_file is not None:
                        mime = image_file.type or "image/png"
                        image_b64 = base64.b64encode(image_file.getvalue()).decode("utf-8")
                        vision_response = client.responses.create(
                            model="gpt-4o-mini",
                            instructions=(
                                "회의 자료를 분석하세요. 주요 논의, 결정사항, 업무, 담당자, 마감일을 정리하세요. "
                                "읽기 어려운 내용은 추측하지 마세요."
                            ),
                            input=[{"role": "user", "content": [
                                {"type": "input_text", "text": "이 회의 자료를 분석해 주세요."},
                                {"type": "input_image", "image_url": f"data:{mime};base64,{image_b64}"},
                            ]}],
                        )
                        image_analysis = vision_response.output_text
                    meeting_analysis = analyze_meeting(client, text, image_analysis)
                    priority_analysis = generate_priorities(client, meeting_analysis)
                    briefing_audio = make_speech(client, priority_analysis)
                st.session_state.meeting_text = text
                st.session_state.image_analysis = image_analysis
                st.session_state.meeting_analysis = meeting_analysis
                st.session_state.priority_analysis = priority_analysis
                st.session_state.briefing_audio = briefing_audio
                st.success("분석 완료! AI 비서와 업무 관리 페이지에서도 결과를 사용할 수 있어요.")
            except Exception as exc:
                st.error(f"분석 중 오류가 발생했습니다: {exc}")

    if st.session_state.image_analysis:
        with st.expander("🖼️ 이미지 분석 결과", expanded=True):
            st.write(st.session_state.image_analysis)
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader("📄 회의록 요약")
        if st.session_state.meeting_analysis:
            show_json_or_text(st.session_state.meeting_analysis)
        else:
            st.info("분석된 회의록이 없습니다.")
    with right:
        st.subheader("📋 업무 우선순위")
        if st.session_state.priority_analysis:
            st.write(st.session_state.priority_analysis)
            if st.session_state.briefing_audio:
                st.audio(st.session_state.briefing_audio, format="audio/mp3")
        else:
            st.info("회의록을 분석하면 우선순위가 표시됩니다.")

elif page == "💬 AI 비서":
    st.caption("회의록 분석 결과를 기억하고 답변합니다. 음성 또는 텍스트로 질문해 보세요.")
    if st.session_state.meeting_analysis:
        st.success("회의록 분석 결과가 연결되어 있습니다.")
    else:
        st.info("회의 자료 없이 일반 질문도 할 수 있습니다.")
    with st.form("assistant_form"):
        question = st.text_area("질문 입력", placeholder="예: 김대리가 해야 할 업무를 알려줘.")
        audio_value = st.audio_input("또는 음성으로 질문하기")
        ask = st.form_submit_button("✨ AI에게 질문", use_container_width=True)
    if ask:
        try:
            client = get_client()
            transcript_text = ""
            if audio_value is not None:
                with st.spinner("음성을 텍스트로 변환 중..."):
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=("audio.wav", audio_value.getvalue(), "audio/wav"),
                    )
                    transcript_text = transcript.text
            user_question = "\n".join(part for part in [question.strip(), transcript_text] if part)
            if not user_question:
                st.warning("텍스트나 음성으로 질문을 입력해 주세요.")
            else:
                context = ""
                if st.session_state.meeting_text:
                    context += "\n\n[회의록 원문]\n" + st.session_state.meeting_text
                if st.session_state.image_analysis:
                    context += "\n\n[이미지 분석]\n" + st.session_state.image_analysis
                if st.session_state.meeting_analysis:
                    context += "\n\n[회의록 분석]\n" + st.session_state.meeting_analysis
                if st.session_state.priority_analysis:
                    context += "\n\n[업무 우선순위]\n" + st.session_state.priority_analysis
                with st.spinner("AI 답변을 준비하는 중..."):
                    response = client.responses.create(
                        model="gpt-4o-mini",
                        instructions=SYS_ROLE + context,
                        input=user_question,
                    )
                    answer = response.output_text
                    audio = make_speech(client, answer)
                st.session_state.assistant_answer = answer
                st.session_state.assistant_audio = audio
                st.session_state.messages.append({"question": user_question, "answer": answer})
        except Exception as exc:
            st.error(f"AI 비서 실행 중 오류가 발생했습니다: {exc}")
    if st.session_state.assistant_answer:
        st.subheader("🤖 AI 답변")
        st.write(st.session_state.assistant_answer)
        if st.session_state.assistant_audio:
            st.audio(st.session_state.assistant_audio, format="audio/mp3")
    if st.session_state.messages:
        with st.expander("최근 질문 기록"):
            for item in reversed(st.session_state.messages[-10:]):
                st.markdown(f"**질문:** {item['question']}")
                st.write(item["answer"])
                st.divider()

elif page == "📋 업무 관리":
    st.caption("회의록에서 추출한 업무와 우선순위를 확인하세요.")
    if st.session_state.priority_analysis:
        st.write(st.session_state.priority_analysis)
        if st.session_state.briefing_audio:
            st.subheader("🔊 오늘의 업무 브리핑")
            st.audio(st.session_state.briefing_audio, format="audio/mp3")
    else:
        st.info("'회의록 분석'에서 자료를 분석하면 업무가 표시됩니다.")

elif page == "⚙️ 설정":
    st.caption("현재 연결된 회의 자료와 세션 데이터를 관리합니다.")
    if st.button("🗑️ 분석 결과와 질문 기록 초기화"):
        for key, default in DEFAULTS.items():
            st.session_state[key] = default
        st.success("현재 세션의 분석 결과와 질문 기록을 초기화했습니다.")
        st.rerun()
