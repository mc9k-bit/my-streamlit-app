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
