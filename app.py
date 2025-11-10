
import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import re

st.set_page_config(layout="wide")

# -----------------------------------------------
# 1. UI/UX 개선: YouTube 톤앤매너 (CSS 주입)
# -----------------------------------------------

st.markdown("""
<style>

h1 {
    text-align: center;
}

div[data-testid="stColumn"]:nth-child(2) {
    text-align: center; /* 컬럼 내부의 모든 인라인 콘텐츠 중앙 정렬 */
}

div[data-testid="stColumn"]:nth-child(2) .stButton {
    display: inline-block; /* text-align: center의 영향을 받도록 변경 */
    margin-top: 10px; /* 검색창과의 간격 추가 */
}

div[data-testid="stColumn"]:nth-child(2) .stButton > button {
    height: 40px;
    background-color: #FF0000; /* YouTube Red */
    color: white;
    border: none;
    border-radius: 4px; /* 약간 둥근 사각형 */
    font-weight: bold;
    padding-left: 1.5rem; /* 버튼 여백 추가 */
    padding-right: 1.5rem; /* 버튼 여백 추가 */
    width: auto; /* (★수정★) 버튼이 내용물 너비만큼만 차지하도록 */
    display: inline-block; /* (★수정★) 중앙 정렬을 위해 */
}
div[data-testid="stColumn"]:nth-child(2) .stButton > button:hover {
    background-color: #CC0000; /* 호버 시 어두운 빨간색 */
    color: white;
}

/* Result video titles (H3) */
.stMarkdown h3 a {
    text-decoration: none; 
    color: #030303;      
    font-weight: bold;
    font-size: 1.1em;
}
.stMarkdown h3 a:hover {
    text-decoration: underline; 
}

/* Metric (조회수, 좋아요) 카드 */
div[data-testid="stMetric"] {
    background-color: #f0f0f0;
    border-radius: 8px;
    padding: 10px;
}
/* Stats Label (e.g., "조회수") */
div[data-testid="stMetricLabel"] {
    font-size: 0.8rem; 
    text-align: right; 
}
/* Stats Value (e.g., "1,234,567") */
div[data-testid="stMetricValue"] {
    font-size: 1.25rem; 
    text-align: right; 
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------
# 2. API  설정
# -----------------------------------------------
try:
    API_KEY = st.secrets["YOUTUBE_API_KEY"]
except KeyError:
    st.error("⚠️ API 키가 설정되지 않았습니다. Colab '비밀' 탭에서 'YOUTUBE_API_KEY'를 추가하세요.")
    st.stop()

# 2. API 빌드 함수 (오류 처리 및 캐싱)
@st.cache_data
def get_youtube_service():
    try:
        return build('youtube', 'v3', developerKey=API_KEY)
    except Exception as e:
        st.error(f"API 연결 실패: {e}")
        return None

# -----------------------------------------------
# 3. 조회 정보 설정
# -----------------------------------------------

# 데이터 검색 함수
@st.cache_data
def search_youtube_videos(search_term):
    youtube = get_youtube_service()
    if youtube is None:
        return pd.DataFrame() # 오류 시 빈 프레임 반환

    one_year_ago = (datetime.utcnow() - timedelta(days=365)).isoformat("T") + "Z"

    # =========================================================================
    # ISO 8601 Duration을 초(seconds)로 변환하는 함수 추가
    # =========================================================================
    def convert_iso8601_to_seconds(duration):
        # 'PT1M30S' -> 90초
        # 'PT45S' -> 45초
        
        # 정규식 패턴: P(일)T(시간)M(분)S(초)
        match = re.match('PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return 0
            
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds
        
    try:
        # API 호출 1: 검색
        search_response = youtube.search().list(
            q=search_term + ' -shorts', # <------------------------ 수정할 부분
            part='snippet',
            type='video',            
            maxResults=50, 
            order='relevance', #연관성
            #order='viewCount',
            publishedAfter=one_year_ago
        ).execute()

        video_ids, channel_ids, video_snippets = [], [], {}
        
        for item in search_response.get('items', []):
            video_id = item['id']['videoId']
            channel_id = item['snippet']['channelId']
            video_ids.append(video_id)
            channel_ids.append(channel_id)
            video_snippets[video_id] = {
                '썸네일': item['snippet']['thumbnails']['medium']['url'],
                '유튜브 링크': f'https://www.youtube.com/watch?v={video_id}',
                '영상 제목': item['snippet']['title'],
                '채널명': item['snippet']['channelTitle'],
                '영상업로드 일자': item['snippet']['publishedAt'].split('T')[0]
            }

        if not video_ids:
            return pd.DataFrame()

        # API 호출 2: 영상 통계
        video_response = youtube.videos().list(
            part='statistics,contentDetails', id=','.join(video_ids) # <-- 수정할 부분
        ).execute()
# 숏츠 필터링용 임시 ID 리스트 및 통계/길이 데이터 딕셔너리
        filtered_video_ids = []
        video_stats = {}
        
        for item in video_response.get('items', []):
            vid = item['id']
            stats = item['statistics']
            duration_iso = item['contentDetails']['duration'] # ISO 8601 길이
            duration_seconds = convert_iso8601_to_seconds(duration_iso)
            
            # ---------------------------------------------------------------------
            # 조건 1: 영상 길이가 60초 초과 (일반 영상)인 경우에만 추가 (<- 수정할 부분)
            # ---------------------------------------------------------------------
            if duration_seconds > 60:
                filtered_video_ids.append(vid)
                video_stats[vid] = {
                    '조회수': int(stats.get('viewCount', 0)),
                    '좋아요수': int(stats.get('likeCount', 0)) if 'likeCount' in stats else '비공개',
                    '영상 길이(초)': duration_seconds # 디버깅용으로 추가 가능
                }

        # 필터링된 ID가 없는 경우
        if not filtered_video_ids:
            return pd.DataFrame()
        
        # ---------------------------------------------------------------------
        # API 호출 3: 채널 통계 (기존 로직 유지)
        # 단, 채널 ID는 필터링된 영상의 채널 ID로 재구성해야 함
        # ---------------------------------------------------------------------
        # 필터링된 영상들만 추려서 채널 ID 목록 재구성
        filtered_channel_ids = []
        for vid in filtered_video_ids:
            # search_response를 다시 순회하며 채널 ID를 찾거나,
            # video_snippets에 채널 ID를 미리 저장해두는 방법도 좋음
            for item in search_response.get('items', []):
                 if item['id']['videoId'] == vid:
                     filtered_channel_ids.append(item['snippet']['channelId'])
                     break
        
        # 채널 ID 중복 제거 후 API 호출
        channel_response = youtube.channels().list(
            part='statistics', id=','.join(list(set(filtered_channel_ids)))
        ).execute()
        
        channel_stats = {}
        for item in channel_response.get('items', []):
            stats = item['statistics']
            channel_stats[item['id']] = {
                '채널구독자수': int(stats.get('subscriberCount', 0)) if not stats.get('hiddenSubscriberCount') else '비공개'
            }

        # ---------------------------------------------------------------------
        # 데이터 취합 (필터링된 ID를 기준으로 취합)
        # ---------------------------------------------------------------------
        final_data = []
        for vid in filtered_video_ids: # <-- 수정된 ID 리스트 사용
            snippet_data = video_snippets.get(vid, {})
            stats_data = video_stats.get(vid, {})
            
            current_channel_id = None
            for item in search_response.get('items', []):
                 if item['id']['videoId'] == vid:
                     current_channel_id = item['snippet']['channelId']
                     break
                     
            channel_data = channel_stats.get(current_channel_id, {})
            
            row = {                 
                '썸네일': snippet_data.get('썸네일'),
                '영상 제목': snippet_data.get('영상 제목'),
                '조회수': stats_data.get('조회수', 0),
                '좋아요수': stats_data.get('좋아요수', '비공개'),
                '채널명': snippet_data.get('채널명'),
                '채널구독자수': channel_data.get('채널구독자수', '비공개'),
                '영상업로드 일자': snippet_data.get('영상업로드 일자'),
                '유튜브 링크': snippet_data.get('유튜브 링크')
            }
            final_data.append(row)

        return pd.DataFrame(final_data)

    except Exception as e:
        st.error(f"API 호출 중 오류 발생: {e}")
        return pd.DataFrame()

# -----------------------------------------------
# 4. 웹페이지 구성
# -----------------------------------------------

st.title("🔍 YouTube 인기 영상 조회")

# 검색창 중앙 정렬을 위한 3단 컬럼 (좌/중앙/우)
left_space, main_search, right_space = st.columns([1, 3, 1])

with main_search:   

    # 1. 검색창 (st.columns 제거)
    search_term = st.text_input(
        "유튜브 검색어를 입력하세요:",
        placeholder="검색", 
        key="search_input",
        on_change=lambda: st.session_state.update(run_search=True),
        label_visibility="collapsed" 
    )

    # 2. 검색 버튼 (st.columns 제거, 텍스트 변경)
    run_button = st.button("검색") 
    
    # 3. 도움말 텍스트 
    st.markdown(
        """
        <p style='text-align: left; font-weight: bold; font-size: 1rem;'>
        ※ 검색어와 연관성이 높고, 최근 1년 영상 중 가장 인기 있는(조회수) 순서로 보여드려요! 📈
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
        with st.spinner(f"'{search_term}'(으)로 데이터를 검색하는 중입니다..."):
            results_df = search_youtube_videos(search_term)
            
            if results_df.empty:
                st.error("검색 결과가 없습니다.")
            else:                
                
                # 조회수 순으로 정렬 (데이터프레임 자체를 정렬)
                results_df_sorted = results_df.sort_values(by='조회수', ascending=False).reset_index(drop=True)

                # 반응형 카드 레이아웃 (st.columns는 모바일에서 자동으로 수직 정렬됨)
                for index, row in results_df_sorted.iterrows():
                    st.write("---") # 구분선
                    
                    # 썸네일 컬럼 | 2. 정보 컬럼
                    c1, c2 = st.columns([1, 3]) 
                    
                    with c1:
                        # 3. 썸네일 추가 (use_column_width -> use_container_width로 수정)
                        st.image(row['썸네일'], use_container_width=True)

                    with c2:
                        # 톤앤매너: 클릭 가능한 제목 (CSS 적용됨)
                        st.markdown(f"### [{row['영상 제목']}]({row['유튜브 링크']})")
                        
                        # 채널명 및 업로드 날짜
                        st.caption(f"{row['채널명']}  ·  {row['영상업로드 일자']}")

                        # 톤앤매너: 통계 정보를 Metric 카드로 표시
                        stats_cols = st.columns(3)
                        
                        # '비공개' 문자열 처리를 위한 함수
                        def format_metric(value):
                            if isinstance(value, (int, float)):
                                return f"{value:,.0f}" # 콤마 + 소수점 없음
                            return value # '비공개' 등 문자열
                        
                        stats_cols[0].metric("조회수", format_metric(row['조회수']))
                        stats_cols[1].metric("좋아요수", format_metric(row['좋아요수']))
                        stats_cols[2].metric("채널구독자수", format_metric(row['채널구독자수']))
                
                
# (%%writefile app.py 명령어가 이 줄에서 종료됩니다)
