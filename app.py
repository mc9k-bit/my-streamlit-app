import base64
import json
import os

import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="ABLE | AI 업무 비서", page_icon="🤖", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px;}
h1, h2, h3 {letter-spacing: -.025em;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 16px;}
</style>
""", unsafe_allow_html=True)

st.title("🤖 ABLE | AI 업무 비서")
st.caption("회의 자료를 분석하고, 업무를 정리하고, 음성으로 브리핑합니다.")

client = OpenAI()

SYS_ROLE = """당신은 친절하고 정확한 한국어 AI 업무 비서입니다.
제공된 회의록과 이미지 분석 자료를 근거로 답변하세요.
근거가 없는 내용은 추측하지 말고, 자료가 있으면 자료를 볼 수 없다고 말하지 마세요."""

with st.container(border=True):
    st.subheader("🎙️ AI 음성 비서")
    with st.form("task_form"):
        file_col, image_col = st.columns(2)
        with file_col:
            uploaded_file = st.file_uploader("회의록 TXT", type=["txt"])
        with image_col:
            image_file = st.file_uploader("회의 자료 이미지", type=["png", "jpg", "jpeg"])
        audio_value = st.audio_input("무엇을 도와드릴까요?")
        submit = st.form_submit_button("✨ 분석 실행", type="primary", use_container_width=True)

if submit:
    if not any([uploaded_file, image_file, audio_value]):
        st.warning("회의록, 이미지 또는 음성 중 하나를 입력해 주세요.")
        st.stop()

    text = ""
    if uploaded_file is not None:
        try:
            text = uploaded_file.getvalue().decode("utf-8-sig")
        except UnicodeDecodeError:
            st.error("TXT 파일을 UTF-8 인코딩으로 저장한 후 다시 업로드해 주세요.")
            st.stop()

    image_analysis = ""
    meeting_result = ""
    priority_result = ""
    answer = ""
    answer_audio = None
    briefing_audio = None

    try:
        if image_file is not None:
            with st.spinner("이미지 분석 중..."):
                image_b64 = base64.b64encode(image_file.getvalue()).decode("ascii")
                mime = image_file.type or "image/png"
                vision_response = client.responses.create(
                    model="gpt-4o-mini",
                    instructions=("회의 자료를 분석하세요. 주요 논의, 결정사항, 업무, 담당자, 마감일을 정리하세요. "
                                  "읽기 어려운 내용은 추측하지 마세요."),
                    input=[{"role": "user", "content": [
                        {"type": "input_text", "text": "이 회의 자료를 분석해 주세요."},
                        {"type": "input_image", "image_url": f"data:{mime};base64,{image_b64}"},
                    ]}],
                )
                image_analysis = vision_response.output_text

        transcript_text = ""
        if audio_value is not None:
            with st.spinner("음성을 텍스트로 변환 중..."):
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=("audio.wav", audio_value.getvalue(), "audio/wav"),
                )
                transcript_text = transcript.text

        reference = ""
        if text:
            reference += f"\n\n[회의록 TXT]\n{text}"
        if image_analysis:
            reference += f"\n\n[이미지 분석 결과]\n{image_analysis}"

        if transcript_text:
            with st.spinner("AI 답변을 준비하는 중..."):
                response = client.responses.create(
                    model="gpt-4o-mini",
                    instructions=SYS_ROLE + reference,
                    input=transcript_text,
                )
                answer = response.output_text
                answer_audio = client.audio.speech.create(
                    model="tts-1", voice="alloy", input=answer
                ).content

        if text or image_analysis:
            with st.spinner("회의록을 구조화하는 중..."):
                meeting_response = client.responses.create(
                    model="gpt-4o-mini",
                    instructions="""당신은 회의록 분석 전문 AI 비서입니다.
회의 내용을 요약하고 주요 논의, 결정사항, 업무, 담당자, 마감일, 예산, 다음 안건을 추출하세요.
원문에 없는 사실은 만들지 마세요. 담당자가 불확실하면 불확실하다고 표시하세요.
반드시 유효한 JSON 객체만 출력하세요. 마크다운 코드 블록을 쓰지 마세요.""",
                    input=f"회의록:\n{text}\n\n이미지 분석:\n{image_analysis}",
                )
                meeting_result = meeting_response.output_text

            with st.spinner("업무 우선순위를 정리하는 중..."):
                priority_response = client.responses.create(
                    model="gpt-4o-mini",
                    instructions="""당신은 업무 일정 관리 전문 AI 비서입니다.
마감일의 임박성, 명시된 중요도, 담당자 확인 여부를 고려해 업무를 우선순위 순으로 정리하세요.
'다음 주'처럼 상대적인 기한을 임의의 날짜로 바꾸지 마세요.
오늘의 업무가 확정되지 않았으면 오늘 확인하거나 준비할 일을 제안하세요.
한국어로 간결하게 작성하고 끝에 '오늘의 업무 브리핑'을 포함하세요.""",
                    input=meeting_result,
                )
                priority_result = priority_response.output_text
                briefing_audio = client.audio.speech.create(
                    model="tts-1", voice="alloy", input=priority_result
                ).content

    except Exception as exc:
        st.error("분석 도중 오류가 발생했습니다. Streamlit 앱 로그를 확인해 주세요.")
        st.stop()

    # 원하는 화면 순서: 음성 답변 → 이미지 분석 → 회의록 / 우선순위
    with st.container(border=True):
        st.subheader("💬 AI 답변")
        if answer:
            st.write(answer)
            if answer_audio:
                st.audio(answer_audio, format="audio/mp3")
        else:
            st.caption("음성 질문을 녹음하면 AI 답변과 음성 재생이 여기에 나타납니다.")

    with st.container(border=True):
        st.subheader("🖼️ 이미지 분석")
        if image_analysis:
            st.write(image_analysis)
        else:
            st.caption("업로드된 이미지가 없거나 분석할 이미지가 없습니다.")

    meeting_col, priority_col = st.columns([3, 2], gap="large")
    with meeting_col:
        with st.container(border=True):
            st.subheader("📋 회의록 요약")
            if meeting_result:
                try:
                    st.json(json.loads(meeting_result))
                except json.JSONDecodeError:
                    st.write(meeting_result)
            else:
                st.caption("회의 자료를 업로드하면 요약이 표시됩니다.")

    with priority_col:
        with st.container(border=True):
            st.subheader("🎯 업무 우선순위")
            if priority_result:
                st.write(priority_result)
                if briefing_audio:
                    st.markdown("**🔊 오늘의 업무 브리핑**")
                    st.audio(briefing_audio, format="audio/mp3")
            else:
                st.caption("회의록 분석 후 업무 우선순위가 표시됩니다.")

