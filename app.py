import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random

st.set_page_config(layout="wide")

# -----------------------------------------------
# 1. UI/UX 개선: CSS (유튜브 스타일 제거 및 일반 UI 유지)
# -----------------------------------------------

st.markdown("""
<style>

h1 {
    text-align: center;
}

div[data-testid="stColumn"]:nth-child(2) {
    text-align: center; 
}

div[data-testid="stColumn"]:nth-child(2) .stButton {
    display: inline-block; 
    margin-top: 10px; 
}

div[data-testid="stColumn"]:nth-child(2) .stButton > button {
    height: 40px;
    background-color: #03C75A; /* Naver Green */
    color: white;
    border: none;
    border-radius: 4px;
    font-weight: bold;
    padding-left: 1.5rem; 
    padding-right: 1.5rem; 
    width: auto;
    display: inline-block;
}
div[data-testid="stColumn"]:nth-child(2) .stButton > button:hover {
    background-color: #02a346; /* 호버 시 어두운 녹색 */
    color: white;
}

/* Result post titles (H3) */
.stMarkdown h3 a {
    text-decoration: none;  
    color: #1a0dab;         /* Google Search Link Blue */
    font-weight: 500;
    font-size: 1.2em;
}
.stMarkdown h3 a:hover {
    text-decoration: underline; 
}

/* 요약/내용 폰트 스타일 */
.summary-text {
    font-size: 0.95rem;
    color: #4d5159; /* Grayish text color */
    line-height: 1.4;
    margin-top: 0.5rem;
    display: -webkit-box;
    -webkit-line-clamp: 3; /* 최대 3줄로 제한 */
    -webkit-box-orient: vertical;
    overflow: hidden;
    text-overflow: ellipsis;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------
# 2. 검색 결과 시뮬레이션 함수 (네이버 블로그 데이터 구조 반영)
# -----------------------------------------------

# API 키 설정 부분은 제거하고, 임시 데이터 함수를 사용합니다.
# 실제 네이버 API 사용 시: Naver Client ID/Secret을 사용하여 API 호출 로직으로 대체해야 합니다.

@st.cache_data
def search_naver_blogs(search_term, max_results=20):
    """
    (Mock Function)
    실제 네이버 API 호출 대신 가상의 블로그 검색 결과를 생성합니다.
    """
    if not search_term:
        return pd.DataFrame()

    today = datetime.now().date()
    
    data = []
    for i in range(1, max_results + 1):
        # 가상의 데이터 생성
        title = f"[{search_term}] 검색 결과 #{i}: 블로그 운영 성공 비법과 후기"
        link = f"https://blog.naver.com/post_id_{i}"
        blogger = f"파워 블로거 {chr(65 + i % 26)}님"
        # 최근 1년 이내 날짜 랜덤 생성
        upload_date = today - timedelta(days=random.randint(1, 365))
        
        # 실제 API의 'description' 필드와 유사하게 내용 요약
        summary = (
            f"안녕하세요, 오늘은 {search_term}에 대한 심층적인 분석을 공유합니다. "
            f"최근 트렌드와 함께 실질적인 적용 팁을 담았습니다. "
            f"이 글이 여러분의 궁금증을 해소하는 데 도움이 되길 바랍니다. "
            f"자세한 내용은 블로그 포스팅에서 확인하세요."
        )

        data.append({
            '블로그 제목': title,
            '블로그 링크': link,
            '요약/내용': summary,
            '블로거': blogger,
            '업로드 일자': upload_date.strftime('%Y.%m.%d'),
            # 네이버 블로그는 조회수/좋아요 대신 댓글 수, 공감 수 등을 사용하지만, 
            # 여기서는 표시하지 않고 간단히 유지합니다.
        })

    return pd.DataFrame(data)

# -----------------------------------------------
# 3. 웹페이지 구성
# -----------------------------------------------

st.title("📚 네이버 블로그 검색 결과 조회")

# 검색창 중앙 정렬을 위한 3단 컬럼 (좌/중앙/우)
left_space, main_search, right_space = st.columns([1, 3, 1])

with main_search:   
    # 1. 검색창 
    search_term = st.text_input(
        "네이버 블로그 검색어를 입력하세요:",
        placeholder="예: 4050 여성 패션", 
        key="search_input",
        on_change=lambda: st.session_state.update(run_search=True),
        label_visibility="collapsed" 
    )

    # 2. 검색 버튼 (텍스트 변경)
    run_button = st.button("네이버 블로그 검색") 
    
    # 3. 도움말 텍스트 
    st.markdown(
        """
        <p style='text-align: left; font-weight: bold; font-size: 1rem;'>
        ※ 입력하신 검색어와 연관된 가상의 네이버 블로그 검색 결과를 보여줍니다. 💻
        </p>
        """,
        unsafe_allow_html=True
    )

# "검색 실행" 버튼 클릭 또는 엔터 입력 시 실행
if run_button or st.session_state.get("run_search"):
    st.session_state["run_search"] = False 

    if not search_term:
        st.warning("검색어를 입력해주세요.")
    else:
        with st.spinner(f"'{search_term}'(으)로 네이버 블로그 검색 결과를 가져오는 중입니다..."):
            # 가상 검색 함수 호출
            results_df = search_naver_blogs(search_term)
            
            if results_df.empty:
                st.error("검색 결과가 없습니다.")
            else:           
                
                # 블로그 결과는 정렬 없이 순서대로 표시 (조회수가 없으므로)
                
                # 반응형 카드 레이아웃
                for index, row in results_df.iterrows():
                    st.write("---") # 구분선
                    
                    # 블로그 글은 썸네일 대신 정보가 더 중요하므로 컬럼 비율 조정
                    # c1 (번호) | c2 (정보)
                    c1, c2 = st.columns([0.5, 3.5]) 
                    
                    with c1:
                        # 순서 번호 표시
                        st.markdown(f"<div style='font-size: 2em; font-weight: bold; color: #03C75A; margin-top: 10px;'>{index + 1}.</div>", unsafe_allow_html=True)

                    with c2:
                        # 톤앤매너: 클릭 가능한 제목 (CSS 적용됨)
                        st.markdown(f"### [{row['블로그 제목']}]({row['블로그 링크']})")
                        
                        # 블로거명 및 업로드 날짜
                        st.caption(f"**{row['블로거']}**  |  {row['업로드 일자']}  |  [원본 블로그 링크]({row['블로그 링크']})")

                        # 요약/내용
                        st.markdown(f"<p class='summary-text'>{row['요약/내용']}</p>", unsafe_allow_html=True)
                        

# (%%writefile naver_blog_search_app.py 명령어가 이 줄에서 종료됩니다)
