import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import re
import urllib.request
import json
import html

# -----------------------------------------------
# 0. 페이지 설정 (가장 먼저 실행되어야 함)
# -----------------------------------------------
st.set_page_config(layout="wide", page_title="YouTube & Naver Search")

# -----------------------------------------------
# 1. UI/UX 개선: CSS 주입
# -----------------------------------------------
st.markdown("""
<style>
h1 { text-align: center; }
/* 검색창 및 버튼 스타일 */
div[data-testid="stColumn"]:nth-child(2) { text-align: center; }
div[data-testid="stColumn"]:nth-child(2) .stButton { display: inline-block; margin-top: 10px; }
div[data-testid="stColumn"]:nth-child(2) .stButton > button {
    height: 40px;
    background-color: #FF0000; /* YouTube Red Style Button */
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
    background-color: #CC0000;
    color: white;
}
/* Result video titles */
.stMarkdown h3 a {
    text-decoration: none; 
    color: #030303;      
    font-weight: bold;
    font-size: 1.1em;
}
.stMarkdown h3 a:hover { text-decoration: underline; }
/* Metric 카드 */
div[data-testid="stMetric"] {
    background-color: #f0f0f0;
    border-radius: 8px;
    padding: 10px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------
# 2. API 키 설정 및 클라이언트 생성
# -----------------------------------------------

# 2-1. YouTube API 설정
try:
    YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]
except KeyError:
    st.error("⚠️ YOUTUBE_API_KEY가 설정되지 않았습니다.")
    st.stop()

# 2-2. Naver API 설정
try:
    NAVER_CLIENT_ID = st.secrets["ilDb5OUSHtH8So32b8G6"]
    NAVER_CLIENT_SECRET = st.secrets["WFuEGiACiQ"]
except KeyError:
    st.error("⚠️ NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET이 설정되지 않았습니다.")
    st.stop()

@st.cache_resource
def get_youtube_service():
    try:
        return build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    except Exception as e:
        st.error(f"YouTube API 연결 실패: {e}")
        return None

# -----------------------------------------------
# 3. 데이터 검색 함수 (YouTube & Naver)
# -----------------------------------------------

# [YouTube] 데이터 검색 함수
@st.cache_data
def search_youtube_videos(search_term):
    youtube = get_youtube_service()
    if youtube is None: return pd.DataFrame()

    one_year_ago = (datetime.utcnow() - timedelta(days=365)).isoformat("T") + "Z"

    def convert_iso8601_to_seconds(duration):
        match = re.match('PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match: return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds
        
    try:
        # 1. 검색 (Shorts 제외 키워드 사용)
        search_response = youtube.search().list(
            q=search_term + ' -shorts',
            part='snippet',
            type='video',            
            maxResults=30, 
            order='relevance',
            publishedAfter=one_year_ago
        ).execute()

        video_ids, video_snippets = [], {}
        for item in search_response.get('items', []):
            video_id = item['id']['videoId']
            video_ids.append(video_id)
            video_snippets[video_id] = {
                '썸네일': item['snippet']['thumbnails']['medium']['url'],
                '유튜브 링크': f'https://www.youtube.com/watch?v={video_id}',
                '영상 제목': html.unescape(item['snippet']['title']),
                '채널명': item['snippet']['channelTitle'],
                '영상업로드 일자': item['snippet']['publishedAt'].split('T')[0],
                'channelId': item['snippet']['channelId']
            }

        if not video_ids: return pd.DataFrame()

        # 2. 영상 통계 조회 (길이 필터링)
        video_response = youtube.videos().list(
            part='statistics,contentDetails', id=','.join(video_ids)
        ).execute()

        filtered_video_ids = []
        video_stats = {}
        
        for item in video_response.get('items', []):
            vid = item['id']
            duration_seconds = convert_iso8601_to_seconds(item['contentDetails']['duration'])
            
            # 60초 초과 영상만 (Shorts 필터링 강화)
            if duration_seconds > 60:
                filtered_video_ids.append(vid)
                video_stats[vid] = {
                    '조회수': int(item['statistics'].get('viewCount', 0)),
                    '좋아요수': int(item['statistics'].get('likeCount', 0)) if 'likeCount' in item['statistics'] else '비공개'
                }

        if not filtered_video_ids: return pd.DataFrame()
        
        # 3. 채널 통계 조회 (구독자 수)
        channel_ids = list(set([video_snippets[vid]['channelId'] for vid in filtered_video_ids]))
        channel_response = youtube.channels().list(
            part='statistics', id=','.join(channel_ids)
        ).execute()
        
        channel_stats = {}
        for item in channel_response.get('items', []):
            sub_count = item['statistics'].get('subscriberCount')
            channel_stats[item['id']] = int(sub_count) if sub_count and not item['statistics'].get('hiddenSubscriberCount') else '비공개'

        # 4. 데이터 병합
        final_data = []
        for vid in filtered_video_ids:
            snip = video_snippets[vid]
            stat = video_stats[vid]
            ch_stat = channel_stats.get(snip['channelId'], '비공개')
            
            final_data.append({
                '썸네일': snip['썸네일'],
                '영상 제목': snip['영상 제목'],
                '조회수': stat['조회수'],
                '좋아요수': stat['좋아요수'],
                '채널명': snip['채널명'],
                '채널구독자수': ch_stat,
                '영상업로드 일자': snip['영상업로드 일자'],
                '유튜브 링크': snip['유튜브 링크']
            })

        return pd.DataFrame(final_data)

    except Exception as e:
        st.error(f"YouTube 검색 오류: {e}")
        return pd.DataFrame()

# [Naver] 블로그 검색 함수
@st.cache_data
def search_naver_blogs(search_term):
    encText = urllib.parse.quote(search_term)
    # 검색 결과 30개, 유사도 순 정렬 (sim) / 날짜순은 (date)
    url = f"https://openapi.naver.com/v1/search/blog?query={encText}&display=30&sort=sim" 
    
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", NAVER_CLIENT_ID)
    request.add_header("X-Naver-Client-Secret", NAVER_CLIENT_SECRET)
    
    try:
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        
        if rescode == 200:
            response_body = response.read()
            data = json.loads(response_body.decode('utf-8'))
            
            blog_list = []
            for item in data['items']:
                # HTML 태그 제거
                clean_title = re.sub('<.+?>', '', item['title'])
                clean_title = html.unescape(clean_title)
                
                # 날짜 포맷 변경 (YYYYMMDD -> YYYY-MM-DD)
                postdate = item['postdate']
                formatted_date = f"{postdate[:4]}-{postdate[4:6]}-{postdate[6:]}"
                
                blog_list.append({
                    '블로그 제목': clean_title,
                    '블로그 주인(이름)': item['bloggername'],
                    '업로드 일자': formatted_date,
                    '링크': item['link']
                })
            return pd.DataFrame(blog_list)
        else:
            st.error(f"Naver API 호출 에러 코드: {rescode}")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Naver 검색 중 오류 발생: {e}")
        return pd.DataFrame()

# -----------------------------------------------
# 4. 웹페이지 구성 (메인 로직)
# -----------------------------------------------

st.title("🔍 통합 인기 검색 (YouTube & Naver)")

# 검색창 영역
left_space, main_search, right_space = st.columns([1, 3, 1])

with main_search:   
    search_term = st.text_input(
        "검색어를 입력하세요:",
        placeholder="검색어 입력", 
        key="search_input",
        label_visibility="collapsed"
    )
    run_button = st.button("통합 검색") 
    
    st.markdown("""
        <p style='text-align: left; font-size: 0.9rem; color: gray;'>
        ※ 버튼 클릭 시 <b>유튜브</b>와 <b>네이버 블로그</b> 결과를 동시에 조회합니다.
        </p>
        """, unsafe_allow_html=True)

# 검색 실행 로직
if run_button:
    if not search_term:
        st.warning("검색어를 입력해주세요.")
    else:
        # 탭 생성
        tab1, tab2 = st.tabs(["🎬 YouTube 영상", "📗 네이버 블로그"])
        
        # 데이터 동시 호출 (순차 실행되지만 사용자 입장에선 한번에 처리됨)
        with st.spinner(f"'{search_term}' 결과를 YouTube와 Naver에서 수집 중입니다..."):
            youtube_df = search_youtube_videos(search_term)
            naver_df = search_naver_blogs(search_term)
            
        # --- [Tab 1] YouTube 결과 렌더링 ---
        with tab1:
            if youtube_df.empty:
                st.info("YouTube 검색 결과가 없습니다.")
            else:
                # 조회수 순 정렬
                youtube_df_sorted = youtube_df.sort_values(by='조회수', ascending=False).reset_index(drop=True)
                
                for index, row in youtube_df_sorted.iterrows():
                    st.write("---")
                    c1, c2 = st.columns([1, 3])
                    
                    with c1:
                        st.image(row['썸네일'], use_container_width=True)
                    
                    with c2:
                        st.markdown(f"### [{row['영상 제목']}]({row['유튜브 링크']})")
                        st.caption(f"{row['채널명']}  ·  {row['영상업로드 일자']}")
                        
                        stats_cols = st.columns(3)
                        def format_metric(value):
                            if isinstance(value, (int, float)):
                                return f"{value:,.0f}"
                            return value
                        
                        stats_cols[0].metric("조회수", format_metric(row['조회수']))
                        stats_cols[1].metric("좋아요수", format_metric(row['좋아요수']))
                        stats_cols[2].metric("구독자수", format_metric(row['채널구독자수']))

        # --- [Tab 2] Naver 블로그 결과 렌더링 ---
        with tab2:
            if naver_df.empty:
                st.info("네이버 블로그 검색 결과가 없습니다.")
            else:
                st.write(f"### '{search_term}' 관련 블로그 포스트")
                
                # 데이터프레임 설정을 통한 표 출력 (링크 클릭 가능하게 설정)
                st.data_editor(
                    naver_df,
                    column_config={
                        "링크": st.column_config.LinkColumn(
                            "보러가기", display_text="게시글 이동"
                        ),
                        "블로그 제목": st.column_config.TextColumn("글 제목", width="large"),
                        "블로그 주인(이름)": st.column_config.TextColumn("블로거", width="medium"),
                        "업로드 일자": st.column_config.TextColumn("작성일", width="small"),
                    },
                    hide_index=True,
                    use_container_width=True
                )
                st.caption("※ 네이버 검색 API 정책상 이웃 수는 제공되지 않아, 블로거 이름과 링크로 대체되었습니다.")
