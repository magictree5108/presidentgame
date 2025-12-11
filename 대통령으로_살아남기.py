import streamlit as st
import pandas as pd
import random
import base64
import os
from datetime import datetime

# =============================================================================
# [1] 기본 설정
# =============================================================================
st.set_page_config(page_title="대통령으로 살아남기", layout="centered")

# 파일 경로
FILE_BGM = "bgm.mp3"
FILE_BG = "background.jpg"
FILE_EMBLEM = "emblem.jpg"
FILE_RANKING = "ranking.csv"

ARCHS = ["자본가", "중산층", "노동자", "빈곤층"]

# =============================================================================
# [2] 핵심 기능 함수
# =============================================================================

def get_base64_file(bin_file):
    if os.path.exists(bin_file):
        try:
            with open(bin_file, 'rb') as f:
                data = f.read()
            return base64.b64encode(data).decode()
        except:
            return None
    return None

def render_bgm():
    b64 = get_base64_file(FILE_BGM)
    if b64:
        st.markdown(f"""
            <div style="margin-bottom: 10px; padding: 10px; background: rgba(0,0,0,0.5); border-radius: 10px;">
                <p style="color:gold; font-weight:bold; margin:0; font-size:0.8rem;">🎵 BGM Playing</p>
                <audio controls autoplay loop style="width:100%; height:30px;">
                    <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                </audio>
            </div>
        """, unsafe_allow_html=True)

def render_background():
    b64 = get_base64_file(FILE_BG)
    if b64:
        st.markdown(
            f'<img src="data:image/jpeg;base64,{b64}" style="width:100%; border-radius:10px; margin-bottom:20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">',
            unsafe_allow_html=True
        )

def get_emblem_tag():
    b64 = get_base64_file(FILE_EMBLEM)
    if b64:
        return f'<img src="data:image/jpeg;base64,{b64}" class="phoenix-logo">'
    else:
        return '<div style="font-size: 60px; margin-bottom: 10px; text-align:center;">🇰🇷</div>'

def update_name():
    st.session_state.player_name = st.session_state.temp_name

def get_crisis_image(idx, default_url):
    local_filename = f"crisis_{idx}.jpg"
    if os.path.exists(local_filename):
        return local_filename
    if default_url:
        return default_url
    return None

# [랭킹 시스템]
def load_ranking():
    if not os.path.exists(FILE_RANKING):
        return pd.DataFrame(columns=["이름", "점수", "칭호", "일시"])
    return pd.read_csv(FILE_RANKING)

def save_ranking(name, score, title):
    df = load_ranking()
    now = datetime.now().strftime("%m-%d %H:%M")
    new_data = pd.DataFrame({"이름": [name], "점수": [score], "칭호": [title], "일시": [now]})
    df = pd.concat([df, new_data], ignore_index=True)
    df = df.sort_values(by="점수", ascending=False)
    df.to_csv(FILE_RANKING, index=False)
    return df

# [정치 성향 분석]
def get_politician_type(stats):
    con_score = stats["자본가"] + stats["중산층"]
    pro_score = stats["노동자"] + stats["빈곤층"]
    diff = pro_score - con_score
    
    if diff > 30: return "진보"
    elif diff > 0: return "중도진보"
    elif diff > -30: return "중도보수"
    else: return "보수"

# =============================================================================
# [3] 게임 데이터
# =============================================================================

ARCH_DESC = {
    "자본가": """
    **💰 [자본가/기업주]**
    - **성향:** 세금 인상과 규제를 극도로 혐오하며, 시장의 자유를 최우선 가치로 둡니다.
    - **위협:** 지지율이 바닥나면 자본을 해외로 빼돌려(Capital Flight) 국가 경제를 마비시킵니다.
    """,
    "중산층": """
    **🏠 [화이트칼라/유주택자]**
    - **성향:** '내 세금이 낭비되는 것'을 가장 싫어하며 부동산과 교육, 물가에 민감합니다.
    - **위협:** 지지율이 바닥나면 대규모 조세 저항 운동과 정권 퇴진 시위를 주도합니다.
    """,
    "노동자": """
    **👷 [블루칼라/임금생활자]**
    - **성향:** 고용 안정과 임금 인상이 생존과 직결됩니다. 쉬운 해고를 두려워합니다.
    - **위협:** 지지율이 바닥나면 국가 기반 시설(철도, 전력)을 멈추는 총파업을 일으킵니다.
    """,
    "빈곤층": """
    **🙏 [기초수급/소외계층]**
    - **성향:** 정부의 복지 지원 없이는 생존이 불가능합니다. 공공 서비스에 전적으로 의존합니다.
    - **위협:** 지지율이 바닥나면 생존을 위해 거리로 뛰쳐나와 걷잡을 수 없는 폭동을 일으킵니다.
    """
}

POLITICIAN_TYPES = {
    "진보": {
        "title": "서민의 벗, 행동하는 양심",
        "models": [
            {"name": "노무현", "img": "https://upload.wikimedia.org/wikipedia/commons/f/f3/Roh_Moo-hyun_Presidential_Portrait.jpg"},
            {"name": "김대중", "img": "https://upload.wikimedia.org/wikipedia/commons/e/ee/Kim_Dae-jung_Official_Portrait.jpg"}
        ],
        "desc": "당신은 서민과 노동자를 위한 정책을 펼쳤습니다. 기득권과의 타협보다는 원칙을 중요시하며, 대중의 뜨거운 지지를 받았습니다."
    },
    "중도진보": {
        "title": "원칙과 포용의 리더십",
        "models": [
            {"name": "문재인", "img": "https://upload.wikimedia.org/wikipedia/commons/3/36/Moon_Jae-in_presidential_portrait.jpg"},
            {"name": "이재명", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/Lee_Jae-myung_%28cropped%29.jpg/440px-Lee_Jae-myung_%28cropped%29.jpg"}
        ],
        "desc": "당신은 개혁을 추구하면서도 안정적인 국정 운영을 시도했습니다. 복지와 공정성을 강조하며 탄탄한 지지층을 확보했습니다."
    },
    "중도보수": {
        "title": "실용주의와 혁신",
        "models": [
            {"name": "안철수", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Ahn_Cheol-soo_portrait.jpg/440px-Ahn_Cheol-soo_portrait.jpg"},
            {"name": "이준석", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Lee_Jun-seok_%28cropped%29.jpg/440px-Lee_Jun-seok_%28cropped%29.jpg"}
        ],
        "desc": "당신은 이념보다는 실용과 과학, 합리성을 중시했습니다. 기존 정치 문법을 깨는 새로운 시도로 중도층의 호응을 얻었습니다."
    },
    "보수": {
        "title": "자유 시장과 법치",
        "models": [
            {"name": "윤석열", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Yoon_Suk-yeol_in_May_2022.jpg/440px-Yoon_Suk-yeol_in_May_2022.jpg"},
            {"name": "김문수", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Kim_Moon-soo_in_October_2024.png/440px-Kim_Moon-soo_in_October_2024.png"}
        ],
        "desc": "당신은 시장의 자유와 튼튼한 안보를 최우선으로 여겼습니다. 기업하기 좋은 나라를 만들고 법과 원칙을 강조했습니다."
    }
}

CRISES_POOL = {
    "초기": [
        {"id": 13, "title": "🍔 프랜차이즈 갑질 파동", "img": "https://images.unsplash.com/photo-1550547660-d9450f859349?q=80&w=800", "desc": "대형 본사의 갑질로 가맹점주가 사망했습니다. 을의 눈물에 국민들이 분노합니다.", "options": [{"name": "규제 3법 통과", "cost": 0, "effect": [-20, 5, 10, 10], "detail": "강력 규제. 재계 반발.", "reason": "자본가-20, 노동자+10"}, {"name": "자율 상생 유도", "cost": 0, "effect": [10, -5, -10, -5], "detail": "기업 자율. 봐주기 논란.", "reason": "자본가+10, 노동자-10"}, {"name": "긴급 대출 지원", "cost": -15, "effect": [-5, 5, 0, 10], "detail": "폐업 방지. 가계부채 증가.", "reason": "빈곤층+10, 국고-15"}]},
        {"id": 14, "title": "📉 코인 거래소 먹튀", "img": "https://images.unsplash.com/photo-1621504450168-38f647319936?q=80&w=800", "desc": "거래소 파산으로 2030 세대 자산이 증발했습니다.", "options": [{"name": "손실 보전", "cost": -25, "effect": [-10, -10, 15, -5], "detail": "세금 투입. 납세자 분노.", "reason": "노동자+15, 중산층-10"}, {"name": "책임 원칙", "cost": 0, "effect": [5, 5, -20, -10], "detail": "투기 경종. 청년 파산.", "reason": "중산층+5, 노동자-20"}, {"name": "규제 강화", "cost": -5, "effect": [-5, 0, -5, 0], "detail": "뒤늦은 규제. 산업 위축.", "reason": "자본가-5, 노동자-5"}]},
        {"id": 3, "title": "🤖 AI 일자리 습격", "img": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?q=80&w=800", "desc": "AI가 인간 업무를 대체하며 고용 불안이 확산됩니다.", "options": [{"name": "로봇세 도입", "cost": -15, "effect": [-20, 5, 10, 10], "detail": "기업 증세.", "reason": "자본가-20, 노동자+10"}, {"name": "규제 철폐", "cost": +10, "effect": [20, 5, -15, -15], "detail": "AI 강국 도약.", "reason": "자본가+20, 노동자-15"}, {"name": "공공 근로", "cost": -20, "effect": [-5, -5, 5, 10], "detail": "단기 일자리.", "reason": "빈곤층+10, 국고-20"}]},
        {"id": 12, "title": "🧬 신약 부작용 사태", "img": "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?q=80&w=800", "desc": "국가 지원 신약의 부작용이 발견되었습니다.", "options": [{"name": "허가 취소", "cost": -20, "effect": [-10, 5, 5, 5], "detail": "안전 우선. 산업 위축.", "reason": "중산층+5, 자본가-10"}, {"name": "인과 규명 우선", "cost": 0, "effect": [10, -10, -10, -5], "detail": "산업 보호. 여론 악화.", "reason": "자본가+10, 중산층-10"}, {"name": "공공 의료 강화", "cost": -30, "effect": [-15, 5, 10, 15], "detail": "공공성 확충. 세금 투입.", "reason": "빈곤층+15, 자본가-15"}]}
    ],
    "중기": [
        {"id": 7, "title": "🏘️ 부동산 시장 대폭락", "img": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?q=80&w=800", "desc": "집값 급락으로 깡통 전세와 건설사 부도가 속출합니다.", "options": [{"name": "부양책", "cost": -10, "effect": [15, 5, -10, -10], "detail": "규제 완화.", "reason": "자본가+15, 노동자-10"}, {"name": "시장 자율", "cost": 0, "effect": [-20, -20, 10, 5], "detail": "거품 붕괴 용인.", "reason": "자본가-20, 노동자+10"}, {"name": "피해 구제", "cost": -20, "effect": [-5, -5, 10, 15], "detail": "세금 지원.", "reason": "빈곤층+15, 국고-20"}]},
        {"id": 9, "title": "⚡ 에너지 위기", "img": "https://images.unsplash.com/photo-1565514020125-998dc57774dc?q=80&w=800", "desc": "유가 폭등으로 난방비 대란이 일어났습니다.", "options": [{"name": "요금 인상", "cost": +10, "effect": [0, -10, -15, -20], "detail": "적자 해소.", "reason": "국고+10, 빈곤층-20"}, {"name": "요금 동결", "cost": -30, "effect": [-5, 10, 10, 10], "detail": "재정 부담.", "reason": "빈곤층+10, 국고-30"}, {"name": "바우처 지급", "cost": -10, "effect": [0, -5, -5, 15], "detail": "선별 지원.", "reason": "빈곤층+15, 노동자-5"}]},
        {"id": 4, "title": "⚔️ 무역 보복 조치", "img": "https://images.unsplash.com/photo-1595246737293-27d096162332?q=80&w=800", "desc": "핵심 소재 수출 금지로 공장이 멈췄습니다.", "options": [{"name": "굴욕적 협상", "cost": 0, "effect": [10, 5, 5, -5], "detail": "실리 추구.", "reason": "자본가+10, 빈곤층-5"}, {"name": "강경 대응", "cost": -10, "effect": [-15, -10, -10, -5], "detail": "자존심.", "reason": "자본가-15, 중산층-10"}, {"name": "국산화 R&D", "cost": -30, "effect": [-5, -5, 5, 0], "detail": "장기 투자.", "reason": "노동자+5, 국고-30"}]},
        {"id": 5, "title": "🏭 기후 재난", "img": "https://images.unsplash.com/photo-1579766922979-4d6cb600259d?q=80&w=800", "desc": "기록적인 폭우와 미세먼지가 덮쳤습니다.", "options": [{"name": "탄소세 도입", "cost": +5, "effect": [-15, -5, 5, 10], "detail": "환경 개선.", "reason": "자본가-15, 빈곤층+10"}, {"name": "경제 우선", "cost": 0, "effect": [15, 5, -10, -20], "detail": "규제 완화.", "reason": "자본가+15, 빈곤층-20"}, {"name": "피해 복구금", "cost": -20, "effect": [-5, 0, 0, 10], "detail": "현금 지급.", "reason": "빈곤층+10, 국고-20"}]},
        {"id": 6, "title": "📉 합계출산율 0.5명", "img": "https://images.unsplash.com/photo-1519689680058-324335c77eba?q=80&w=800", "desc": "국가 소멸 위기론이 대두되었습니다.", "options": [{"name": "현금 지원", "cost": -30, "effect": [-5, 10, 5, -5], "detail": "양육비 확대.", "reason": "중산층+10, 빈곤층-5"}, {"name": "이민청 설립", "cost": -5, "effect": [10, -10, -10, 5], "detail": "노동력 수입.", "reason": "자본가+10, 노동자-10"}, {"name": "연금 개혁", "cost": +10, "effect": [-5, -15, -15, -5], "detail": "고통 분담.", "reason": "중산층-15, 국고+10"}]}
    ],
    "말기": [
        {"id": 0, "title": "📉 글로벌 복합 금융 위기", "img": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=800", "desc": "환율 1,500원 돌파. 국가 부도 위기설.", "options": [{"name": "법인세 인하", "cost": -10, "effect": [15, 5, -10, -15], "detail": "낙수효과.", "reason": "자본가+15, 빈곤층-15"}, {"name": "재난지원금", "cost": -30, "effect": [-15, 5, 10, 20], "detail": "내수 방어.", "reason": "빈곤층+20, 자본가-15"}, {"name": "고금리 긴축", "cost": +10, "effect": [5, -20, -10, -5], "detail": "물가 안정.", "reason": "자본가+5, 중산층-20"}]},
        {"id": 2, "title": "📢 광화문 100만 촛불", "img": "https://images.unsplash.com/photo-1563986768609-322da13575f3?q=80&w=800", "desc": "정권 퇴진을 요구하는 100만 인파가 집결했습니다.", "options": [{"name": "증세 및 복지", "cost": +20, "effect": [-25, -5, 10, 20], "detail": "요구 수용.", "reason": "빈곤층+20, 자본가-25"}, {"name": "공권력 투입", "cost": -5, "effect": [15, 5, -20, -15], "detail": "강제 진압.", "reason": "자본가+15, 노동자-20"}, {"name": "대국민 사과", "cost": 0, "effect": [-10, 5, 5, 5], "detail": "내각 사퇴.", "reason": "자본가-10, 중산층+5"}]},
        {"id": 10, "title": "💣 북한 국지적 도발", "img": "https://images.unsplash.com/photo-1554223249-1755a5b512c8?q=80&w=800", "desc": "휴전선 포격 도발. 전쟁 위기 고조.", "options": [{"name": "강력 응징", "cost": -20, "effect": [5, -5, -5, -5], "detail": "원점 타격.", "reason": "자본가+5, 중산층-5"}, {"name": "대화 시도", "cost": 0, "effect": [-15, 5, 5, 5], "detail": "확전 방지.", "reason": "자본가-15, 빈곤층+5"}, {"name": "국방비 증액", "cost": -30, "effect": [-5, -10, -15, -5], "detail": "군비 강화.", "reason": "노동자-15, 국고-30"}]},
        {"id": 8, "title": "🕵️ 권력형 비리 게이트", "img": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?q=80&w=800", "desc": "측근 비리 발각으로 도덕성에 치명타.", "options": [{"name": "성역 없는 수사", "cost": 0, "effect": [-15, 10, 10, 0], "detail": "읍참마속.", "reason": "중산층+10, 자본가-15"}, {"name": "정치 탄압 주장", "cost": 0, "effect": [5, -20, -20, -5], "detail": "지지층 결집.", "reason": "자본가+5, 중산층-20"}, {"name": "제도 개혁 약속", "cost": -10, "effect": [-5, 5, 5, 0], "detail": "시선 분산.", "reason": "중산층+5, 자본가-5"}]},
        {"id": 1, "title": "🦠 치명적 신종 바이러스", "img": "https://images.unsplash.com/photo-1584036561566-baf8f5f1b144?q=80&w=800", "desc": "전염병 확산으로 의료 체계 붕괴.", "options": [{"name": "국가 봉쇄", "cost": -10, "effect": [-5, -10, -15, 5], "detail": "경제 마비.", "reason": "빈곤층+5, 노동자-15"}, {"name": "위드 코로나", "cost": 0, "effect": [10, 5, 0, -25], "detail": "경제 우선.", "reason": "자본가+10, 빈곤층-25"}, {"name": "치료제 무상", "cost": -40, "effect": [-5, 5, 5, 15], "detail": "재정 투입.", "reason": "빈곤층+15, 국고-40"}]}
    ]
}

# =============================================================================
# [4] 메인 로직
# =============================================================================

# 초기화
if 'turn' not in st.session_state:
    st.session_state.turn = 1
    st.session_state.stats = {k: 50 for k in ARCHS}
    st.session_state.budget = 100
    st.session_state.game_over = False
    st.session_state.fail_msg = ""
    st.session_state.logs = []
    st.session_state.player_name = "성명을 입력하세요"
    st.session_state.temp_name = st.session_state.player_name
    st.session_state.current_crisis = random.choice(CRISES_POOL["초기"])

def restart():
    st.session_state.clear()
    st.rerun()

def next_turn(idx):
    opt = st.session_state.current_crisis['options'][idx]
    st.session_state.budget += opt['cost']
    for i, a in enumerate(ARCHS):
        st.session_state.stats[a] = max(0, min(100, st.session_state.stats[a] + opt['effect'][i]))
    
    st.session_state.logs.append(f"Turn {st.session_state.turn}: {opt['name']} 선택")
    
    # 게임 오버 체크
    if st.session_state.budget < 0:
        st.session_state.game_over = True
        st.session_state.fail_msg = "💸 국가 부도 선언 (국고 고갈)"
    elif any(v <= 0 for v in st.session_state.stats.values()):
        st.session_state.game_over = True
        st.session_state.fail_msg = "🔥 대규모 폭동 발생 (지지율 0%)"
    elif st.session_state.turn >= 10:
        st.session_state.game_over = True
        st.session_state.fail_msg = "🎉 임기 5년 만료"
    else:
        st.session_state.turn += 1
        # 시기에 맞는 이벤트 선택
        turn = st.session_state.turn
        if turn <= 3: pool = CRISES_POOL["초기"]
        elif turn <= 7: pool = CRISES_POOL["중기"]
        else: pool = CRISES_POOL["말기"]
        
        st.session_state.current_crisis = random.choice(pool)

# UI 렌더링
render_bgm()
render_background()

st.markdown("""
    <style>
        .nameplate {
            background-color: #003478; border: 4px solid #c2a042;
            padding: 15px; border-radius: 10px; text-align: center;
            margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.5);
            display: flex; flex-direction: column; align-items: center;
        }
        .nameplate h3 { color: #c2a042 !important; margin: 0; font-weight: bold; font-size: 1.5rem; letter-spacing: 2px; }
        .nameplate h1 { color: white !important; margin: 5px 0 0 0; font-family: 'serif'; font-size: 2.8rem; font-weight: bold; text-shadow: 2px 2px 4px black; }
    </style>
""", unsafe_allow_html=True)

emblem_tag = get_emblem_tag()
st.markdown(f'''
<div class="nameplate">
    {emblem_tag}
    <h3>대한민국 대통령</h3>
    <h1>{st.session_state.player_name}</h1>
</div>
''', unsafe_allow_html=True)

st.title("🏛️ 대통령으로 살아남기")

# 사이드바
with st.sidebar:
    st.header("1. 대통령 취임")
    st.text_input("성함 입력 (엔터치면 반영):", key="temp_name", on_change=update_name)
    
    if "load_ranking" in globals() and os.path.exists(FILE_RANKING):
        st.markdown("---")
        st.subheader("🏆 명예의 전당 (Top 5)")
        df_rank = load_ranking()
        if not df_rank.empty:
            st.dataframe(df_rank[["이름", "점수", "칭호"]].head(5), hide_index=True)

    st.markdown("---")
    st.header("ℹ️ 계층 가이드")
    with st.expander("❓ 계층별 핵심 이익 보기"):
        for k, v in ARCH_DESC.items():
            st.markdown(f"{v}")
            st.markdown("---")

# HUD
cols = st.columns(5)
cols[0].metric("국고", f"{st.session_state.budget}조")
for i, a in enumerate(ARCHS):
    cols[i+1].metric(f"{a} 지지율", f"{st.session_state.stats[a]}%")

if not st.session_state.game_over:
    st.write(f"### 🗓️ 임기 {st.session_state.turn}년차 / 총 10년 (남은 안건: {11 - st.session_state.turn}개)")
    st.progress(min(1.0, (st.session_state.turn - 1) / 10))

st.markdown("---")

# 게임 화면
if st.session_state.game_over:
    if "성공" in st.session_state.fail_msg or "만료" in st.session_state.fail_msg:
        st.balloons()
        st.success(f"🏆 {st.session_state.fail_msg}")
    else:
        st.error(f"💀 GAME OVER: {st.session_state.fail_msg}")

    # 최종 점수 계산
    avg = sum(st.session_state.stats.values()) / 4
    budget = st.session_state.budget
    st.markdown(f"### 📊 최종 성적: 평균 지지율 {avg:.1f}% / 국고 {budget}조")

    # 정치인 유형 분석
    my_type = get_politician_type(st.session_state.stats)
    p_data = POLITICIAN_TYPES[my_type]
    
    st.markdown("---")
    st.subheader(f"🧩 당신의 정치 성향: [{my_type}]")
    st.write(f"**\"{p_data['title']}\"**")
    st.info(p_data['desc'])
    
    st.write("#### 👥 당신과 비슷한 현실 정치인")
    pc1, pc2 = st.columns(2)
    with pc1:
        st.image(p_data['models'][0]['img'], caption=p_data['models'][0]['name'])
    with pc2:
        st.image(p_data['models'][1]['img'], caption=p_data['models'][1]['name'])

    st.markdown("---")

    # 지지층 분석
    sorted_stats = sorted(st.session_state.stats.items(), key=lambda x: x[1])
    best = sorted_stats[-1]
    worst = sorted_stats[0]
    
    col_a, col_b = st.columns(2)
    col_a.metric("❤️ 핵심 지지층", f"{best[0]} ({best[1]}%)")
    col_b.metric("💔 최대 비토층", f"{worst[0]} ({worst[1]}%)")

    # 랭킹 저장 (Top 10 표시 포함)
    if "load_ranking" in globals() and os.path.exists(FILE_RANKING):
        st.markdown("---")
        st.subheader("🏆 명예의 전당 (Top 10)")
        df_rank = load_ranking()
        if not df_rank.empty:
            st.dataframe(df_rank.head(10), hide_index=True)

    if "score_saved" not in st.session_state:
        final_score = int(sum(st.session_state.stats.values()) / 4 + st.session_state.budget)
        final_title = "대통령"
        if "성공" not in st.session_state.fail_msg and "만료" not in st.session_state.fail_msg:
            final_title = "불명예 퇴진"
            final_score = int(final_score / 2)
        
        save_ranking(st.session_state.player_name, final_score, final_title)
        st.session_state.score_saved = True

    if st.button("🔄 다시 하기 (재당선 도전)"):
        restart()
        
    with st.expander("📜 지난 기록 보기"):
        for log in st.session_state.logs:
            st.write(log)

else:
    c = st.session_state.current_crisis
    st.error(f"🚨 [속보] {c['title']}")
    
    img_url = get_crisis_image(c.get('id', 99), c.get('img'))
    if img_url:
        st.image(img_url, use_container_width=True)
        
    st.write(f"### {c['desc']}")
    
    col1, col2, col3 = st.columns(3)
    for i, opt in enumerate(c['options']):
        with [col1, col2, col3][i]:
            st.info(f"{opt['name']}")
            st.caption(f"📝 {opt['detail']}")
            sign = "+" if opt['cost'] > 0 else ""
            st.write(f"💰 **국고 {sign}{opt['cost']}조**")
            if st.button(f"승인 ({i+1})", key=f"btn_{st.session_state.turn}_{i}"):
                next_turn(i)
                st.rerun()
