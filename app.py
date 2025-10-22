
import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from datetime import datetime, timedelta

st.set_page_config(layout="wide")

# 1. UI/UX 개선: YouTube 톤앤매너 (CSS 주입)
st.markdown("""
<style>
/* YouTube Red Button */
.stButton > button {
    background-color: #FF0000;
    color: white;
    border: none;
    border-radius: 4px;
    font-weight: bold;
}
.stButton > button:hover {
    background-color: #CC0000;
    color: white;
}

/* Result video titles (H3) */
.stMarkdown h3 a {
    text-decoration: none; /* 밑줄 제거 */
    color: #030303;      /* 유튜브 제목 색상 */
    font-weight: bold;
    font-size: 1.2em;
}
.stMarkdown h3 a:hover {
    text-decoration: underline; /* 마우스 올리면 밑줄 */
}

/* Metric (조회수, 좋아요) 카드 */
div[data-testid="stMetric"] {
    background-color: #f0f0f0;
    border-radius: 8px;
    padding: 10px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------
# 1. API 키 설정
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

# 3. 데이터 검색 함수
@st.cache_data
def search_youtube_videos(search_term):
    youtube = get_youtube_service()
    if youtube is None:
        return pd.DataFrame() # 오류 시 빈 프레임 반환

    one_year_ago = (datetime.utcnow() - timedelta(days=365)).isoformat("T") + "Z"

    try:
        # API 호출 1: 검색
        search_response = youtube.search().list(
            q=search_term,
            part='snippet',
            type='video',            
            maxResults=50, # <-- 10에서 50으로 변경            
            order='viewCount',
            publishedAfter=one_year_ago
        ).execute()

        video_ids, channel_ids, video_snippets = [], [], {}
        # (이하 코드는 동일합니다)
        ...
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
            part='statistics', id=','.join(video_ids)
        ).execute()
        video_stats = {}
        for item in video_response.get('items', []):
            stats = item['statistics']
            video_stats[item['id']] = {
                '조회수': int(stats.get('viewCount', 0)),
                '좋아요수': int(stats.get('likeCount', 0)) if 'likeCount' in stats else '비공개',
            }

        # API 호출 3: 채널 통계
        channel_response = youtube.channels().list(
            part='statistics', id=','.join(list(set(channel_ids)))
        ).execute()
        channel_stats = {}
        for item in channel_response.get('items', []):
            stats = item['statistics']
            channel_stats[item['id']] = {
                '채널구독자수': int(stats.get('subscriberCount', 0)) if not stats.get('hiddenSubscriberCount') else '비공개'
            }

        # 데이터 취합
        final_data = []
        for vid in video_ids:
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

#     # 4. 스타일 적용 함수
# def style_dataframe(df):    
#     def make_clickable(url_str):        
#         return f'<a href="{url_str}" target="_blank">영상보러가기</a>' # <-- 수정된 코드    
    
#     # 1. 정렬을 먼저 수행합니다.
#     if '조회수' in df.columns:
#         df_sorted = df.sort_values(by='조회수', ascending=False).reset_index(drop=True)
#     else:
#         df_sorted = df.reset_index(drop=True) # 정렬할 게 없어도 인덱스 리셋

#     # 2. 정렬이 완료된 데이터프레임을 복사합니다.
#     df_to_style = df_sorted.copy()
    
#     # 3. 복사본에 링크 서식을 적용합니다.
#     df_to_style['유튜브 링크'] = df_to_style['유튜브 링크'].apply(make_clickable)
#     numeric_cols = ['조회수', '좋아요수', '채널구독자수']

#     def make_clickable(url_str):        
#         return f'<a href="{url_str}" target="_blank">영상보러가기</a>' # <-- 수정된 코드
    
#     # 1. 정렬을 먼저 수행합니다.
#     if '조회수' in df.columns:
#         df_sorted = df.sort_values(by='조회수', ascending=False).reset_index(drop=True)
#     else:
#         df_sorted = df.reset_index(drop=True) # 정렬할 게 없어도 인덱스 리셋

#     # 2. 정렬이 완료된 데이터프레임을 복사합니다.
#     df_to_style = df_sorted.copy()
    
#     # 3. 복사본에 링크 서식을 적용합니다.
#     df_to_style['유튜브 링크'] = df_to_style['유튜브 링크'].apply(make_clickable)

#     numeric_cols = ['조회수', '좋아요수', '채널구독자수']
    
#     # 4. 스타일을 적용합니다.
#     styled = df_to_style.style \
#         .hide(axis="index") \
#         .format(
#             # 값이 숫자인 경우(int, float)에만 콤마 서식을 적용하고,
#             # '비공개' 같은 문자열은 그대로 둡니다.
#             formatter=lambda x: f"{x:,}" if isinstance(x, (int, float)) else x, 
#             subset=numeric_cols
#         ) \
#         .set_properties(
#             subset=numeric_cols, **{'text-align': 'right'} # 1. 숫자 우측 정렬
#         ) \
#         .set_properties(
#             subset=['채널명'], **{'text-align': 'center'} # 2. 채널명 중앙 정렬
#         ) \
#         .set_properties(
#             subset=['영상 제목', '유튜브 링크'], **{'text-align': 'left'} # 3. 영상 제목/링크 좌측 정렬
#         ) \
#         .set_table_styles([
#             {'selector': 'th', 'props': [('text-align', 'center')]} # 4. 헤더 중앙 정렬
#         ])    
    
#     return styled

# 5. Streamlit 웹페이지 구성
st.title("📈 유튜브 검색 결과 조회")

# 2. 검색창과 버튼을 한 줄에 배치
col1, col2 = st.columns([5, 1]) # 5:1 비율로 컬럼 분할

with col1:
    search_term = st.text_input(
        "유튜브 검색어를 입력하세요:",
        key="search_input",
        on_change=lambda: st.session_state.update(run_search=True),
        label_visibility="collapsed" # '유튜브 검색어를 입력하세요:' 레이블 숨김
    )

with col2:
    run_button = st.button("검색 실행")

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

                # 4. 반응형 카드 레이아웃 (st.columns는 모바일에서 자동으로 수직 정렬됨)
                for index, row in results_df_sorted.iterrows():
                    st.write("---") # 구분선
                    
                    # 1. 썸네일 컬럼 | 2. 정보 컬럼
                    c1, c2 = st.columns([1, 3]) 
                    
                    with c1:
                        # 3. 썸네일 추가
                        st.image(row['썸네일'], use_column_width=True)

                    with c2:
                        # 1. 톤앤매너: 클릭 가능한 제목 (CSS 적용됨)
                        st.markdown(f"### [{row['영상 제목']}]({row['유튜브 링크']})")
                        
                        # 채널명 및 업로드 날짜
                        st.caption(f"{row['채널명']}  ·  {row['영상업로드 일자']}")

                        # 1. 톤앤매너: 통계 정보를 Metric 카드로 표시
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
