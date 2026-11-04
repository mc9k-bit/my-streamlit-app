
import os, base64, json, requests
import streamlit as st
from openai import OpenAI

# OpenAI 클라이언트 생성
client = OpenAI()

# 페이지 설정
st.set_page_config(page_title="음성 AI 서비스", page_icon="🤖", layout="wide")
st.title("음성 인식 AI 서비스")
st.write("음성으로 질문하시면 답변해 드립니다.")

# 역할 지정
sys_role = """
당신은 다양한 업무를 처리하는 AI 서비스입니다.
개인 비서처럼 친절하게 응대합니다.
"""

# 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 지시 영역
with st.form("task_form"):
    uploaded_file = st.file_uploader("텍스트 파일 업로드", type=["txt"])

    image_file = st.file_uploader(
        "회의 자료 이미지 업로드",
        type=["png", "jpg", "jpeg"]
    )

    audio_value = st.audio_input("무엇을 도와드릴까요?")
    submit = st.form_submit_button("실행")

# 버튼을 눌렀을 때만 실행
if submit:
    # 업로드 된 파일이 있으면 디코딩
    text = ""
    if uploaded_file is not None:
        text = uploaded_file.read().decode("utf-8")

    # 녹음이 없으면 녹음 요청
    if audio_value is None:
        st.warning("음성을 녹음해주세요.")
        st.stop()

    # 시스템 메세지
    system_content = sys_role
    if text:
        system_content += f"\n\n다음 내용을 참고하세요:\n{text}"
    input_messages = [{"role": "system", "content": system_content}]

    
    # 이미지 분석 기능
    image_analysis = ""

    if image_file is not None:
        image_bytes = image_file.getvalue()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        mime_type = image_file.type

        vision_response = client.responses.create(
            model="gpt-4o-mini",
            instructions="""
            당신은 회의 자료 분석 전문 AI입니다.
            이미지에 포함된 텍스트와 주요 내용을 분석하세요.
            결정사항, 업무, 담당자, 마감일을 구분하세요.
            읽기 어려운 내용은 추측하지 마세요.
            """,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "이 회의 자료 이미지를 분석해 주세요."
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{image_base64}"
                        }
                    ]
                }
            ]
        )

        image_analysis = vision_response.output_text

        st.subheader("이미지 분석 결과")
        st.write(image_analysis)


    # STT: 음성 → 텍스트
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=("audio.wav", audio_value, "audio/wav"))

    # 사용자 메시지
    input_messages.append({"role": "user", "content": transcript.text})

    

    # LLM 호출 및 응답 듣기
    with st.spinner("답변을 준비하고 있습니다..."):
        response = client.responses.create(
            model="gpt-4o-mini",
            input=input_messages
        )
        answer = response.output_text

        # AI 텍스트 답변
        st.subheader("AI 답변")
        st.write(answer)

        
       
        # 회의록 분석 기능
        if text:
            meeting_response = client.responses.create(
                model="gpt-4o-mini",
                instructions="""
                당신은 회의록 분석 전문 AI 비서입니다.
                회의 내용을 요약하고,
                결정사항과 담당 업무, 마감일을 추출하세요.
                회의록에 없는 내용은 만들지 마세요.
                반드시 유효한 JSON 객체만 출력하세요.
                마크다운 코드 블록은 사용하지 마세요.
                """,
                input=f"회의록:\n{text}\n\n이미지 분석 결과:\n{image_analysis}"
            )

            st.subheader("회의록 분석 결과")
            st.write(meeting_response.output_text)

            
            # 업무 우선순위 분석
            priority_response = client.responses.create(
                model="gpt-4o-mini",
                instructions="""
                당신은 업무 일정 관리 전문 AI 비서입니다.

                회의록 분석 결과를 바탕으로 업무 우선순위를 정하세요.

                기준:
                1. 마감일이 임박한 업무를 우선합니다.
                2. 중요하다고 강조된 업무를 우선합니다.
                3. 담당자가 명확한 업무를 구분합니다.
                4. 마감일이 불명확하면 추측하지 않습니다.
                5. 오늘 할 일이 확정되지 않았다면
                   오늘 확인하거나 준비할 업무를 제안합니다.

                우선순위가 높은 순서대로 업무를 정리하고,
                마지막에 오늘의 업무 브리핑을 작성하세요.
                """,
                input=meeting_response.output_text
            )

            # 우선순위 결과 출력
            st.subheader("업무 우선순위")
            st.write(priority_response.output_text)

            # 오늘의 업무 브리핑 음성 생성
            briefing_speech = client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=priority_response.output_text
            )

            st.subheader("오늘의 업무 브리핑")
            st.audio(briefing_speech.content, format="audio/mp3")


        


        # TTS: 텍스트를 음성으로 변환
        speech = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=answer
        )

        # 음성 재생
        st.audio(speech.content, format="audio/mp3")


