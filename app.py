
import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from datetime import datetime, timedelta

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
            maxResults=10,
            order='viewCount',
            publishedAfter=one_year_ago
        ).execute()

        video_ids, channel_ids, video_snippets = [], [], {}
        for item in search_response.get('items', []):
            video_id = item['id']['videoId']
            channel_id = item['snippet']['channelId']
            video_ids.append(video_id)
            channel_ids.append(channel_id)
            video_snippets[video_id] = {
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

# 4. 스타일 적용 함수
def style_dataframe(df):
    
    def make_clickable(url_str):
        return f'<a href="{url_str}" target="_blank">{url_str}</a>'      

    # 1. 정렬을 먼저 수행합니다.
    if '조회수' in df.columns:
        df_sorted = df.sort_values(by='조회수', ascending=False).reset_index(drop=True)
    else:
        df_sorted = df.reset_index(drop=True) # 정렬할 게 없어도 인덱스 리셋

    # 2. 정렬이 완료된 데이터프레임을 복사합니다.
    df_to_style = df_sorted.copy()
    
    # 3. 복사본에 링크 서식을 적용합니다.
    df_to_style['유튜브 링크'] = df_to_style['유튜브 링크'].apply(make_clickable)

    numeric_cols = ['조회수', '좋아요수', '채널구독자수']

    # 4. 스타일을 적용합니다.
    styled = df_to_style.style \
        .hide(axis="index") \
        .format(subset=numeric_cols, formatter='{:,}') \
        .set_properties(
            subset=numeric_cols, **{'text-align': 'right'} # 1. 숫자 우측 정렬
        ) \
        .set_properties(
            subset=['채널명'], **{'text-align': 'center'} # 2. 채널명 중앙 정렬
        ) \
        .set_properties(
            subset=['영상 제목', '유튜브 링크'], **{'text-align': 'left'} # 3. 영상 제목/링크 좌측 정렬
        ) \
        .set_table_styles([
            {'selector': 'th', 'props': [('text-align', 'center')]} # 4. 헤더 중앙 정렬
        ])    
    
    return styled

# 5. Streamlit 웹페이지 구성
st.title("📈 유튜브 검색 결과 조회")

# 검색어 입력
search_term = st.text_input(
    "유튜브 검색어를 입력하세요:",
    key="search_input", # 엔터 키 감지를 위한 고유 키
    on_change=lambda: st.session_state.update(run_search=True) # 엔터 시 검색 트리거
)

# "검색 실행" 버튼
if st.button("검색 실행") or st.session_state.get("run_search"):
    st.session_state["run_search"] = False # 검색 트리거 초기화

    if not search_term:
        st.warning("검색어를 입력해주세요.")
    else:
        with st.spinner(f"'{search_term}'(으)로 데이터를 검색하는 중입니다..."):
            results_df = search_youtube_videos(search_term)
            
            if results_df.empty:
                st.error("검색 결과가 없습니다.")
            else:
                # --- ▼▼▼ 이 아랫부분을 교체하세요 ▼▼▼ ---
                
                # 1. 위에서 수정한 style_dataframe 함수로 스타일 적용
                styled_results = style_dataframe(results_df)

                # 2. HTML로 변환하여 출력 (st.dataframe 대신 다시 이 방법 사용)
                st.write(styled_results.to_html(escape=False), unsafe_allow_html=True)

                # --- ▲▲▲ 여기까지 교체하세요 ▲▲▲ ---

# (%%writefile app.py 명령어가 이 줄에서 종료됩니다)
