
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
    
    df_to_style = df.copy()
    df_to_style['유튜브 링크'] = df_to_style['유튜브 링크'].apply(make_clickable)

    numeric_cols = ['조회수', '좋아요수', '채널구독자수']

    styled = df_to_style.style \
        .hide(axis="index") \ # <-- 이 줄을 추가하여 첫 열(인덱스)을 숨깁니다.
        .format(subset=numeric_cols, formatter='{:,}') \
        .set_properties(subset=numeric_cols, **{'text-align': 'right'}) \
        .set_properties(subset=['영상 제목', '유튜브 링크'], **{'text-align': 'left'}) \
        .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center')]}])
    
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
                # 1. 첫 열 (인덱스) 삭제 및 스타일링 적용
                # 2. 반응형 테이블 및 컬럼 사이즈 조절 (st.dataframe 활용)
                #    st.dataframe은 자동으로 반응형을 지원합니다.
                #    컬럼 너비는 "column_config"로 조절할 수 있습니다.

                # 조회수, 좋아요수, 구독자수 포매터 함수
                def format_numeric(value):
                    if isinstance(value, (int, float)):
                        return f"{value:,}"
                    return value

                st.dataframe(
                    results_df,
                    use_container_width=True, # 부모 컨테이너 너비에 맞춰 자동 조절
                    hide_index=True, # 첫 열(인덱스) 삭제
                    column_config={
                        "유튜브 링크": st.column_config.LinkColumn(
                            "유튜브 링크",
                            help="클릭 시 유튜브 영상으로 이동합니다.",
                            display_text="유튜브 링크", # 컬럼에 표시될 텍스트
                        ),
                        "영상 제목": st.column_config.Column(
                            "영상 제목",
                            width="large", # 너비 조절 (small, medium, large, custom)
                        ),
                        "조회수": st.column_config.NumberColumn(
                            "조회수",
                            format="%d", # 천단위 콤마는 아래에서 직접 적용
                        ),
                        "좋아요수": st.column_config.NumberColumn(
                            "좋아요수",
                            format="%d",
                        ),
                        "채널명": st.column_config.Column(
                            "채널명",
                            width="medium",
                        ),
                        "채널구독자수": st.column_config.NumberColumn(
                            "채널구독자수",
                            format="%d",
                        ),
                        "영상업로드 일자": st.column_config.DateColumn(
                            "영상업로드 일자",
                            format="YYYY-MM-DD",
                        ),
                    }
                )

                # st.dataframe은 셀 정렬이나 숫자 콤마 포맷팅을 column_config 내에서 직접적으로 지원하지 않아,
                # 필요시 수동 포맷팅 로직을 추가해야 합니다.
                # 그러나 st.dataframe은 기본적으로 LinkColumn 등을 통해 유용한 기능을 제공합니다.

                # Styler를 사용한 기존 방식은 반응형 테이블이 아니며,
                # Streamlit의 최신 st.dataframe 기능과 함께 사용하기 어렵습니다.
                # 따라서, st.dataframe의 기본 스타일링을 활용하는 것을 권장합니다.
                
                # 만약 이전 Styler 방식의 세밀한 정렬과 포맷팅이 꼭 필요하다면,
                # st.dataframe 대신 df.style.to_html(escape=False)를 사용해야 하며,
                # 이 경우 반응형과 컬럼 사이즈 조절은 CSS를 직접 추가해야 하는 어려움이 있습니다.
                # 여기서는 st.dataframe의 장점을 살린 방식으로 제공합니다.

# (%%writefile app.py 명령어가 이 줄에서 종료됩니다)
