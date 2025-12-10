# 1. 기존 파일 삭제 및 초기화
import os
os.system("rm -f app.py")
os.system("pip install -q streamlit")

# 2. app.py 작성 (문법 오류 수정됨)
code = """
import streamlit as st
import pandas as pd
import random
import base64
import os

# -----------------------------------------------------------------------------
# [설정] 파일 경로 (GitHub 배포 시에도 이 파일들이 같이 있어야 함)
# -----------------------------------------------------------------------------
FILE_BGM = "bgm.mp3"
FILE_BG = "background.jpg"
FILE_EMBLEM = "emblem.jpg"

ARCHS = ["자본가", "중산층", "노동자", "빈곤층"]

# [함수] 로컬 파일 -> Base64 변환
def get_base64_file(bin_file):
    if os.path.exists(bin_file):
        try:
            with open(bin_file, 'rb') as f:
                data = f.read()
            return base64.b64encode(data).decode()
        except:
            return None
    return None

# [함수] BGM 재생기 (따옴표 수정됨)
def render_bgm():
    b64 = get_base64_file(FILE_BGM)
    if b64:
        # 여기서 문법 오류가 났었습니다. 작은따옴표(''')로 변경하여 해결!
        st.markdown(f'''
            <div style="margin-bottom: 10px; padding: 10px; background: rgba(0,0,0,0.5); border-radius: 10px;">
                <p style="color:gold; font-weight:bold; margin:0; font-size:0.8rem;">🎵 BGM Loaded</p>
                <audio controls autoplay loop style="width:100%; height:30px;">
                    <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                </audio>
            </div>
        ''', unsafe_allow_html=True)

# [함수] 배경 이미지 렌더링
def render_background():
    b64 = get_base64_file(FILE_BG)
    if b64:
        st.markdown(
            f'<img src="data:image/jpeg;base64,{b64}" style="width:100%; border-radius:10px; margin-bottom:20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">',
            unsafe_allow_html=True
        )

# [함수] 명패 이미지 태그 (파일 있으면 쓰고 없으면 태극기)
def get_emblem_tag():
    b64 = get_base64_file(FILE_EMBLEM)
    if b64:
        return f'<img src="data:image/jpeg;base64,{b64}" class="phoenix-logo">'
    else:
        # 파일 없으면 태극기 이모지 사용
        return '<div style="font-size: 50px; margin-bottom: 10px;">🇰🇷</div>'

# 계층 설명
ARCH_DESC = {
    "자본가": "💰 **[자본가/기업주]** 세금과 규제를 혐오하며, 자산 가치 보전을 최우선으로 합니다.",
    "중산층": "🏠 **[화이트칼라/유주택자]** '열심히 일하는데 국가가 세금으로 다 가져간다'는 불만이 큽니다. 집값과 교육, 물가에 민감합니다.",
    "노동자": "👷 **[블루칼라/임금생활자]** 자산보다는 '월급'과 '고용 안정'이 생명입니다. 노동권과 임금 인상을 원합니다.",
    "빈곤층": "🙏 **[기초수급/소외계층]** 국가의 복지 없이는 생존이 불가능합니다. 현금 지원과 공공 서비스가 절실합니다."
}

# 이벤트 리스트 (15종)
CRISES_POOL = [
    {"title": "📉 글로벌 복합 금융 위기", "desc": "금리 인상으로 주가 폭락, 환율 1,500원 돌파.", "options": [
        {"name": "법인세 인하", "cost": -10, "effect": [15, 5, -10, -15], "detail": "기업 세금을 깎아 투자를 유도합니다.", "reason": "자본가+15 (감세), 빈곤층-15 (복지축소)"},
        {"name": "재난지원금 살포", "cost": -30, "effect": [-15, 5, 10, 20], "detail": "국채 발행해 현금을 풉니다.", "reason": "빈곤층+20 (현금), 자본가-15 (인플레)"},
        {"name": "고금리 긴축", "cost": +10, "effect": [5, -20, -10, -5], "detail": "허리띠를 졸라매 물가를 잡습니다.", "reason": "자본가+5 (방어), 중산층-20 (이자폭탄)"}
    ]},
    {"title": "🦠 치명적 신종 바이러스", "desc": "전염병 확산. 병상 포화 및 공포 확산.", "options": [
        {"name": "국가 봉쇄", "cost": -10, "effect": [-5, -10, -15, 5], "detail": "강력 봉쇄로 방역 성공하나 생계 마비.", "reason": "빈곤층+5 (생명), 노동자-15 (실직)"},
        {"name": "위드 코로나", "cost": 0, "effect": [10, 5, 0, -25], "detail": "경제는 돌지만 취약계층 사망 급증.", "reason": "자본가+10 (매출), 빈곤층-25 (사망)"},
        {"name": "치료제 무상공급", "cost": -40, "effect": [-5, 5, 5, 15], "detail": "막대한 예산으로 생명 보호.", "reason": "빈곤층+15 (치료), 국고-40 (지출)"}
    ]},
    {"title": "📢 광화문 100만 촛불", "desc": "정부 실정에 분노한 시민들의 퇴진 시위.", "options": [
        {"name": "부자 증세/복지", "cost": +20, "effect": [-25, -5, 10, 20], "detail": "요구 수용. 서민 환호, 자본가 이탈.", "reason": "빈곤층+20 (혜택), 자본가-25 (세금)"},
        {"name": "공권력 투입", "cost": -5, "effect": [15, 5, -20, -15], "detail": "강제 해산. 보수 결집, 중도 이탈.", "reason": "자본가+15 (질서), 노동자-20 (탄압)"},
        {"name": "대국민 사과", "cost": 0, "effect": [-10, 5, 5, 5], "detail": "사과 및 개각. 식물 정부 위기.", "reason": "자본가-10 (무능), 중산층+5 (소통)"}
    ]},
    {"title": "🤖 AI 일자리 습격", "desc": "AI가 인간 업무 대체. 고용 불안 공포.", "options": [
        {"name": "로봇세 도입", "cost": -15, "effect": [-20, 5, 10, 10], "detail": "기업에 세금 물려 실직자 지원.", "reason": "자본가-20 (규제), 노동자+10 (안전망)"},
        {"name": "규제 철폐", "cost": +10, "effect": [20, 5, -15, -15], "detail": "AI 강국 도약, 노동자 빈곤화.", "reason": "자본가+20 (이익), 노동자-15 (해고)"},
        {"name": "공공 근로", "cost": -20, "effect": [-5, -5, 5, 10], "detail": "세금으로 단기 일자리 급조.", "reason": "빈곤층+10 (생계), 국고-20 (지출)"}
    ]},
    {"title": "⚔️ 무역 보복 조치", "desc": "외교 갈등으로 핵심 소재 수출 금지.", "options": [
        {"name": "굴욕적 협상", "cost": 0, "effect": [10, 5, 5, -5], "detail": "요구 들어주고 수출 재개.", "reason": "자본가+10 (회복), 빈곤층-5 (자존심)"},
        {"name": "강경 대응", "cost": -10, "effect": [-15, -10, -10, -5], "detail": "자존심 지키나 경제 고통 심화.", "reason": "자본가-15 (매출), 중산층-10 (물가)"},
        {"name": "국산화 R&D", "cost": -30, "effect": [-5, -5, 5, 0], "detail": "기술 독립 선언. 당장은 예산 출혈.", "reason": "노동자+5 (일자리), 국고-30 (지출)"}
    ]},
    {"title": "🏭 미세먼지와 기후 재난", "desc": "최악의 대기질과 폭우 동시 발생.", "options": [
        {"name": "탄소세 도입", "cost": +5, "effect": [-15, -5, 5, 10], "detail": "환경 개선, 기업 비용 증가.", "reason": "자본가-15 (비용), 빈곤층+10 (안전)"},
        {"name": "경제 우선", "cost": 0, "effect": [15, 5, -10, -20], "detail": "규제 완화. 서민 주거지 침수.", "reason": "자본가+15 (이익), 빈곤층-20 (피해)"},
        {"name": "피해 복구금", "cost": -20, "effect": [-5, 0, 0, 10], "detail": "현금 지급. 근본 해결 안됨.", "reason": "빈곤층+10 (구제), 국고-20 (지출)"}
    ]},
    {"title": "📉 합계출산율 0.5명", "desc": "국가 소멸 위기 및 연금 고갈 공포.", "options": [
        {"name": "현금 지원 확대", "cost": -30, "effect": [-5, 10, 5, -5], "detail": "양육비 지원. 노인 예산 삭감.", "reason": "중산층+10 (양육), 빈곤층-5 (삭감)"},
        {"name": "이민청 설립", "cost": -5, "effect": [10, -10, -10, 5], "detail": "외국인 노동자 수용.", "reason": "자본가+10 (인력), 노동자-10 (경쟁)"},
        {"name": "연금 개혁", "cost": +10, "effect": [-5, -15, -15, -5], "detail": "보험료 인상. 직장인 분노.", "reason": "중산층-15 (부담), 국고+10 (재정)"}
    ]},
    {"title": "🏘️ 부동산 대폭락", "desc": "집값 급락, 깡통 전세 및 건설사 부도.", "options": [
        {"name": "부양책", "cost": -10, "effect": [15, 5, -10, -10], "detail": "규제 완화로 집값 방어.", "reason": "자본가+15 (방어), 노동자-10 (박탈)"},
        {"name": "시장 자율", "cost": 0, "effect": [-20, -20, 10, 5], "detail": "거품 붕괴 방관. 경기 침체.", "reason": "자본가-20 (폭락), 노동자+10 (내집)"},
        {"name": "전세 피해 구제", "cost": -20, "effect": [-5, -5, 10, 15], "detail": "세금으로 보증금 지원.", "reason": "빈곤층+15 (구제), 국고-20 (세금)"}
    ]},
    {"title": "🕵️ 권력형 비리 게이트", "desc": "측근 비리 발각. 공정성 시비.", "options": [
        {"name": "성역 없는 수사", "cost": 0, "effect": [-15, 10, 10, 0], "detail": "철저 수사. 당내 기반 약화.", "reason": "중산층+10 (공정), 자본가-15 (반발)"},
        {"name": "정치 탄압 주장", "cost": 0, "effect": [5, -20, -20, -5], "detail": "지지층 결집, 중도 이탈.", "reason": "자본가+5 (결집), 중산층-20 (실망)"},
        {"name": "제도 개혁 약속", "cost": -10, "effect": [-5, 5, 5, 0], "detail": "미래 약속으로 시선 분산.", "reason": "중산층+5 (기대), 자본가-5 (피로)"}
    ]},
    {"title": "⚡ 에너지 위기", "desc": "유가 폭등. 난방비 대란 및 한전 적자.", "options": [
        {"name": "요금 인상", "cost": +10, "effect": [0, -10, -15, -20], "detail": "적자 해소. 서민 고통 가중.", "reason": "국고+10 (건전성), 빈곤층-20 (위협)"},
        {"name": "요금 동결", "cost": -30, "effect": [-5, 10, 10, 10], "detail": "세금으로 방어. 부채 급증.", "reason": "빈곤층+10 (안도), 국고-30 (부채)"},
        {"name": "바우처 지급", "cost": -10, "effect": [0, -5, -5, 15], "detail": "취약계층만 선별 지원.", "reason": "빈곤층+15 (생존), 노동자-5 (소외)"}
    ]},
    {"title": "💣 북한 국지적 도발", "desc": "휴전선 포격. 안보 불안 고조.", "options": [
        {"name": "강력 응징", "cost": -20, "effect": [5, -5, -5, -5], "detail": "단호 대처. 전쟁 공포 확산.", "reason": "자본가+5 (안보), 중산층-5 (주가)"},
        {"name": "대화 시도", "cost": 0, "effect": [-15, 5, 5, 5], "detail": "확전 방지. 굴종 논란.", "reason": "자본가-15 (실망), 빈곤층+5 (평화)"},
        {"name": "국방비 증액", "cost": -30, "effect": [-5, -10, -15, -5], "detail": "자주 국방 강화. 민생 소홀.", "reason": "노동자-15 (민생), 국고-30 (지출)"}
    ]},
    {"title": "🚢 대형 해상 참사", "desc": "대형 인명 사고. 국가 안전 불신.", "options": [
        {"name": "전면 안전 감찰", "cost": -10, "effect": [-10, 5, 5, 5], "detail": "안전 점검 강화. 기업 피로.", "reason": "자본가-10 (규제), 중산층+5 (안전)"},
        {"name": "배상 및 추모", "cost": -15, "effect": [-5, 0, 0, 5], "detail": "유가족 위로. 세금 논란.", "reason": "빈곤층+5 (위로), 자본가-5 (피로)"},
        {"name": "실무자 처벌", "cost": 0, "effect": [0, -10, -10, -5], "detail": "꼬리 자르기. 불신 심화.", "reason": "중산층-10 (불신), 노동자-10 (분노)"}
    ]},
    {"title": "🧬 신약 부작용", "desc": "국책 신약 부작용. 피해자 소송.", "options": [
        {"name": "허가 취소", "cost": -20, "effect": [-10, 5, 5, 5], "detail": "국민 안전 우선. 산업 위축.", "reason": "중산층+5 (신뢰), 자본가-10 (하락)"},
        {"name": "신중 모드", "cost": 0, "effect": [10, -10, -10, -5], "detail": "산업 보호. 생명 경시 비판.", "reason": "자본가+10 (보호), 중산층-10 (비판)"},
        {"name": "공공 의료 강화", "cost": -30, "effect": [-15, 5, 10, 15], "detail": "공공성 확충. 조세 저항.", "reason": "빈곤층+15 (혜택), 자본가-15 (세금)"}
    ]},
    {"title": "🍔 프랜차이즈 갑질", "desc": "가맹점주 사망. 경제 민주화 요구.", "options": [
        {"name": "규제 3법", "cost": 0, "effect": [-20, 5, 10, 10], "detail": "강력 규제. 기업 투자 위축.", "reason": "자본가-20 (규제), 노동자+10 (보호)"},
        {"name": "자율 상생", "cost": 0, "effect": [10, -5, -10, -5], "detail": "자율에 맡김. 봐주기 의혹.", "reason": "자본가+10 (자유), 노동자-10 (실망)"},
        {"name": "긴급 대출", "cost": -15, "effect": [-5, 5, 0, 10], "detail": "폐업 방지. 가계 부채 증가.", "reason": "빈곤층+10 (생존), 국고-15 (지출)"}
    ]},
    {"title": "📉 코인 거래소 파산", "desc": "거래소 먹튀. 청년 자산 증발.", "options": [
        {"name": "손실 보전", "cost": -25, "effect": [-10, -10, 15, -5], "detail": "세금으로 피해를 보전해줍니다. 청년 파산은 막았으나, '도박 빚을 갚아주냐'는 성실 납세자들의 분노가 폭발했습니다.", "reason": "노동자+15 (구제), 중산층-10 (분노)"},
        {"name": "책임 원칙", "cost": 0, "effect": [5, 5, -20, -10], "detail": "투기 수요에 경종을 울렸습니다. 하지만 전 재산을 잃은 청년층이 대거 신용불량자로 전락하며 사회적 활력이 급격히 떨어집니다.", "reason": "중산층+5 (원칙), 노동자-20 (파산)"},
        {"name": "규제 강화", "cost": -5, "effect": [-5, 0, -5, 0], "detail": "뒤늦게 규제 장벽을 세웠습니다. 시장은 건전해졌지만, '소 잃고 외양간 고치기'라는 비판과 함께 산업 위축을 가져왔습니다.", "reason": "자본가-5 (규제), 노동자-5 (뒷북)"}
    ]}
]

# -----------------------------------------------------------------------------
# [메인 로직]
# -----------------------------------------------------------------------------
st.set_page_config(page_title="미스터 프레지던트: 리부트", layout="centered")

# 배경음악/사진 렌더링
render_bgm()
render_background()

# 상태 초기화
if 'turn' not in st.session_state:
    st.session_state.turn = 1
    st.session_state.stats = {k: 50 for k in ARCHS}
    st.session_state.budget = 100
    st.session_state.game_over = False
    st.session_state.logs = []
    st.session_state.player_name = "각하"
    st.session_state.current_crisis = random.choice(CRISES_POOL)

# 턴 넘기기
def next_turn(idx):
    opt = st.session_state.current_crisis['options'][idx]
    st.session_state.budget += opt['cost']
    for i, a in enumerate(ARCHS):
        st.session_state.stats[a] = max(0, min(100, st.session_state.stats[a] + opt['effect'][i]))
    
    st.session_state.logs.append(f"Turn {st.session_state.turn}: {opt['name']} 선택")
    
    if st.session_state.budget < 0:
        st.session_state.game_over = True
        st.session_state.fail_msg = "💸 국가 부도 선언 (국고 고갈)"
    elif any(v <= 0 for v in st.session_state.stats.values()):
        st.session_state.game_over = True
        st.session_state.fail_msg = "🔥 대규모 폭동 발생 (지지율 0%)"
    elif st.session_state.turn >= 10:
        st.session_state.game_over = True
        st.session_state.fail_msg = "🎉 임기 5년 무사 만료"
    else:
        st.session_state.turn += 1
        st.session_state.current_crisis = random.choice(CRISES_POOL)

# UI: 명패 및 상태바
st.markdown(\"\"\"
    <style>
        .nameplate {
            background-color: #003478; border: 4px solid #c2a042;
            padding: 15px; border-radius: 10px; text-align: center;
            margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.5);
        }
        .phoenix-logo { width: 100px; margin-bottom: 10px; display: block; margin-left: auto; margin-right: auto; }
        .nameplate h4 { color: #c2a042 !important; margin: 0; font-weight: bold; font-size: 1.1rem; letter-spacing: 2px; }
        .nameplate h2 { color: white !important; margin: 5px 0 0 0; font-family: 'serif'; font-size: 2.0rem; font-weight: bold; text-shadow: 2px 2px 4px black; }
    </style>
\"\"\", unsafe_allow_html=True)

emblem_tag = get_emblem_tag()
st.markdown(f'''
<div class="nameplate">
    {emblem_tag}
    <h4>대한민국 대통령</h4>
    <h2>{st.session_state.player_name}</h2>
</div>
''', unsafe_allow_html=True)

st.title("🏛️ 미스터 프레지던트")

# 사이드바
with st.sidebar:
    st.header("1. 대통령 취임")
    name = st.text_input("성함 입력 (엔터치면 반영):", value=st.session_state.player_name)
    if name: st.session_state.player_name = name
    
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
    cols[i+1].metric(a, f"{st.session_state.stats[a]}%")

st.markdown("---")

# 게임 화면
if st.session_state.game_over:
    if "성공" in st.session_state.fail_msg or "만료" in st.session_state.fail_msg:
        st.balloons()
        st.success(f"🏆 {st.session_state.fail_msg}")
        avg = sum(st.session_state.stats.values()) / 4
        st.write(f"### 📊 최종 지지율: {avg:.1f}%")
        
        st.subheader("📰 [호외] 임기 종료 특별 보도")
        if avg >= 70: st.success(f"🌟 역사에 남을 성군, {st.session_state.player_name} 대통령 퇴임")
        elif avg < 40: st.error(f"💀 역대 최저 지지율... 쓸쓸한 퇴장")
        else: st.info(f"⚖️ 공과 과 남기고 떠나는 {st.session_state.player_name} 대통령")
        
    else:
        st.error(f"💀 GAME OVER: {st.session_state.fail_msg}")
    
    if st.button("🔄 다시 하기"):
        st.session_state.clear()
        st.rerun()
        
    with st.expander("📜 지난 기록 보기"):
        for log in st.session_state.logs:
            st.write(log)

else:
    c = st.session_state.current_crisis
    st.error(f"🚨 [속보] {c['title']}")
    st.write(c['desc'])
    
    col1, col2, col3 = st.columns(3)
    for i, opt in enumerate(c['options']):
        with [col1, col2, col3][i]:
            st.info(f"{opt['name']}")
            st.caption(opt['detail'])
            sign = "+" if opt['cost'] > 0 else ""
            st.write(f"**국고 {sign}{opt['cost']}조**")
            if st.button(f"승인 ({i+1})", key=f"btn_{st.session_state.turn}_{i}"):
                next_turn(i)
                st.rerun()
"""

with open("app.py", "w") as f:
    f.write(code)

# 2. requirements.txt (필수)
with open("requirements.txt", "w") as f:
    f.write("streamlit\npandas\n")

# 3. Cloudflare 실행
!wget -q -O cloudflared-linux-amd64 https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
!chmod +x cloudflared-linux-amd64
!nohup ./cloudflared-linux-amd64 tunnel --url http://localhost:8501 > cloudflared.log 2>&1 &
!sleep 5

print("👇 아래 링크를 클릭하세요 (v36.0: 문법 오류 수정 완료):")
!grep -o 'https://.*\.trycloudflare.com' cloudflared.log | head -n 1
!streamlit run app.py &>/dev/null
