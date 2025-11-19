import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import re
import urllib.request
import json
import html

# -----------------------------------------------
# 0. 페이지 설정
# -----------------------------------------------
st.set_page_config(layout="wide", page_title="YouTube & Naver Search")

# -----------------------------------------------
# 1. API 키 설정 (하드코딩 방식)
# -----------------------------------------------
# 주의: 이 파일은 GitHub 등 공개된 저장소에 올리면 안 됩니다.

# [YouTube API 키 입력]
# 기존처럼 secrets를 쓰시려면 아래 줄을 주석 처리하고 try-except를 쓰세요.
# 지금은 하드코딩 예시입니다.
YOUTUBE_API_KEY = st.secrets["YOUTUBE_API_KEY"]

# [Naver API 키 입력]
# 'NAVER_CLIENT_ID 또는...' 에러가 안 나도록 try-except 구문을 제거했습니다.
NAVER_CLIENT_ID = "ilDb5OUSHtH8So32b8G6"
NAVER_CLIENT_SECRET = "WFuEGiACiQ"


# -----------------------------------------------
# 2. UI/UX 스타일 (CSS)
# -----------------------------------------------
st.markdown("""
<style>
h1 { text-align: center; }
div[data-testid="stColumn"]:nth-child(2) { text-align: center; }
div[data-testid="stColumn"]:nth-child(2) .stButton { display: inline-block; margin-top: 10px; }
div[data-testid="stColumn"]:nth-child(2) .stButton > button {
    height: 40px;
    background-color: #FF0000;
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
.stMarkdown h3 a {
    text-decoration: none; 
    color: #030303;      
    font-weight: bold;
    font-size: 1.1em;
}
.stMarkdown h3 a:hover { text-decoration: underline; }
div[data-testid="stMetric"] {
    background-color: #f0f0f0;
    border-radius: 8px;
    padding: 10px;
}
/* [추가됨] HTML 블로그 테이블 스타일 */
.blog-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
}
.blog-table th {
    background-color: #f0f2f6;
    color: #31333F;
    font-weight: bold;
    padding: 12px;
    text-align: center; /* 좌측 정렬에서 중앙 정렬로 변경 */
    border-bottom: 2px solid #ddd;
}
.blog-table td {
    padding: 12px;
    border-bottom: 1px solid #eee;
    font-size: 0.95rem;
    text-align: center; /* 데이터 셀 중앙 정렬 추가 */
}
.blog-table tr:hover {
    background-color: #f9f9f9;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------
# 3. 데이터 검색 함수
# -----------------------------------------------

@st.cache_resource
def get_youtube_service():
    try:
        return build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    except Exception as e:
        st.error(f"YouTube API 연결 실패: {e}")
        return None

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

        video_response = youtube.videos().list(
            part='statistics,contentDetails', id=','.join(video_ids)
        ).execute()

        filtered_video_ids = []
        video_stats = {}
        
        for item in video_response.get('items', []):
            vid = item['id']
            duration_seconds = convert_iso8601_to_seconds(item['contentDetails']['duration'])
            
            if duration_seconds > 60:
                filtered_video_ids.append(vid)
                video_stats[vid] = {
                    '조회수': int(item['statistics'].get('viewCount', 0)),
                    '좋아요수': int(item['statistics'].get('likeCount', 0)) if 'likeCount' in item['statistics'] else '비공개'
                }

        if not filtered_video_ids: return pd.DataFrame()
        
        channel_ids = list(set([video_snippets[vid]['channelId'] for vid in filtered_video_ids]))
        channel_response = youtube.channels().list(
            part='statistics', id=','.join(channel_ids)
        ).execute()
        
        channel_stats = {}
        for item in channel_response.get('items', []):
            sub_count = item['statistics'].get('subscriberCount')
            channel_stats[item['id']] = int(sub_count) if sub_count and not item['statistics'].get('hiddenSubscriberCount') else '비공개'

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

@st.cache_data
def search_naver_blogs(search_term):
    # API 키가 하드코딩 되어있는지 확인 (None이거나 비어있으면 실행 안 함)
    if not NAVER_CLIENT_ID or "여기에" in NAVER_CLIENT_ID:
        return pd.DataFrame()

    encText = urllib.parse.quote(search_term)
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
                clean_title = re.sub('<.+?>', '', item['title'])
                clean_title = html.unescape(clean_title)
                
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
# 4. 웹페이지 메인 로직
# -----------------------------------------------

st.title("🔍 통합 인기 검색 (YouTube & Naver)")

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
        ※ 버튼 클릭 시 <b>유튜브</b>와 <b>네이버 블로그</b> 결과를 동시에 조회합니다. </br>
        ※ 유튜브 영상은 검색어와 연관성이 높고, 최근 1년 영상 중 가장 인기 있는(조회수) 순서로 보여드려요! Shorts 영상은 제외 됩니다. 📈
        </p>
        """, unsafe_allow_html=True)

if run_button:
    if not search_term:
        st.warning("검색어를 입력해주세요.")
    else:
        tab1, tab2 = st.tabs(["🎬 YouTube 영상", "📗 네이버 블로그"])
        
        with st.spinner(f"'{search_term}' 결과를 수집 중입니다..."):
            # 데이터 수집
            youtube_df = search_youtube_videos(search_term)
            naver_df = search_naver_blogs(search_term)
            
        # [Tab 1] YouTube
        with tab1:
            if youtube_df.empty:
                st.info("YouTube 검색 결과가 없습니다 (또는 API 키 확인 필요).")
            else:
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
                        
                        # 숫자 포맷팅 (비공개 처리)
                        view_count = f"{row['조회수']:,.0f}" if isinstance(row['조회수'], (int, float)) else row['조회수']
                        like_count = f"{row['좋아요수']:,.0f}" if isinstance(row['좋아요수'], (int, float)) else row['좋아요수']
                        sub_count = f"{row['채널구독자수']:,.0f}" if isinstance(row['채널구독자수'], (int, float)) else row['채널구독자수']

                        stats_cols[0].metric("조회수", view_count)
                        stats_cols[1].metric("좋아요수", like_count)
                        stats_cols[2].metric("구독자수", sub_count)

        # [Tab 2] Naver 블로그 (수정된 부분)
        with tab2:
            if naver_df.empty:
                st.info("네이버 블로그 검색 결과가 없습니다 (또는 API 키 확인 필요).")
            else:
                st.write(f"### 📗 '{search_term}' 관련 블로그 포스트")
                
                # 1. [수정] '블로그 제목' 컬럼을 클릭 가능한 HTML 태그(<a>)로 변환
                # target="_blank"는 새 창에서 열기를 의미합니다.
                naver_df['블로그 제목'] = naver_df.apply(
                    lambda x: f'<a href="{x["링크"]}" target="_blank">{x["블로그 제목"]}</a>', 
                    axis=1
                )

                # 2. [수정] '링크' 컬럼(보러가기)은 삭제하고, 화면에 보여줄 컬럼만 선택
                display_df = naver_df[['블로그 제목', '블로그 주인(이름)', '업로드 일자']]

                # 3. [수정] DataFrame을 HTML 테이블로 변환하여 렌더링
                # escape=False: HTML 태그를 텍스트가 아닌 코드로 인식하게 함
                # index=False: 불필요한 인덱스 번호 제거
                html_table = display_df.to_html(escape=False, index=False, classes="blog-table")
                st.markdown(html_table, unsafe_allow_html=True)

                st.caption("※ 제목을 클릭하면 해당 블로그 게시물로 이동합니다.")
