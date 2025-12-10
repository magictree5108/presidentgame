import streamlit as st
import pandas as pd
import random
import base64
import os

# =============================================================================
# [1] 기본 설정 (맨 처음에 실행)
# =============================================================================
st.set_page_config(page_title="미스터 프레지던트", layout="centered")

# 파일 경로
FILE_BGM = "bgm.mp3"
FILE_BG = "background.jpg"
FILE_EMBLEM = "emblem.jpg"

ARCHS = ["자본가", "중산층", "노동자", "빈곤층"]

# =============================================================================
# [2] 핵심 기능 함수들 (여기에 다 모아둠 - NameError 방지)
# =============================================================================

def get_base64_file(bin_file):
    """파일을 읽어서 웹에서 쓸 수 있는 코드로 변환"""
    if os.path.exists(bin_file):
        try:
            with open(bin_file, 'rb') as f:
                data = f.read()
            return base64.b64encode(data).decode()
        except:
            return None
    return None

def render_bgm():
    """배경음악 재생"""
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
    """배경화면 설정"""
    b64 = get_base64_file(FILE_BG)
    if b64:
        st.markdown(
            f'<img src="data:image/jpeg;base64,{b64}" style="width:100%; border-radius:10px; margin-bottom:20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);">',
            unsafe_allow_html=True
        )

def get_emblem_tag():
    """명패 이미지 태그 생성"""
    b64 = get_base64_file(FILE_EMBLEM)
    if b64:
        return f'<img src="data:image/jpeg;base64,{b64}" class="phoenix-logo">'
    else:
        return '<div style="font-size: 60px; margin-bottom: 10px;">🇰🇷</div>'

def update_name():
    """이름 입력 시 즉시 반영"""
    st.session_state.player_name = st.session_state.temp_name

# ★ [문제 해결] 오류가 났던 함수를 확실하게 정의함
def get_crisis_image(idx, default_url):
    """이벤트별 이미지 가져오기 (파일 우선 -> 웹 URL)"""
    # 1. 사용자가 올린 crisis_0.jpg 같은 파일이 있는지 확인
    local_filename = f"crisis_{idx}.jpg"
    if os.path.exists(local_filename):
        return local_filename
    
    # 2. 없으면 기본 웹 이미지 URL 사용
    if default_url:
        return default_url
    
    # 3. 그것도 없으면 None
    return None

# =============================================================================
# [3] 게임 데이터 (텍스트 & 이미지 링크)
# =============================================================================

ARCH_DESC = {
    "자본가": """
    **💰 [자본가/기업주]**
    - **성향:** 세금 인상과 규제를 극도로 혐오하며, 시장의 자유를 최우선 가치로 둡니다.
    - **위협:** 지지율이 바닥나면 자본을 해외로 빼돌려(Capital Flight) 국가 경제를 마비시킵니다.
    - **요구:** 법인세 인하, 노동 유연화, 규제 철폐
    """,
    "중산층": """
    **🏠 [화이트칼라/유주택자]**
    - **성향:** '내 세금이 낭비되는 것'을 가장 싫어하며 부동산과 교육, 물가에 민감합니다.
    - **위협:** 지지율이 바닥나면 대규모 조세 저항 운동과 정권 퇴진 시위를 주도합니다.
    - **요구:** 자산 가치 보전, 물가 안정, 공정성 확립
    """,
    "노동자": """
    **👷 [블루칼라/임금생활자]**
    - **성향:** 고용 안정과 임금 인상이 생존과 직결됩니다. 쉬운 해고를 두려워합니다.
    - **위협:** 지지율이 바닥나면 국가 기반 시설(철도, 전력)을 멈추는 총파업을 일으킵니다.
    - **요구:** 고용 보장, 최저임금 인상, 노동권 강화
    """,
    "빈곤층": """
    **🙏 [기초수급/소외계층]**
    - **성향:** 정부의 복지 지원 없이는 생존이 불가능합니다. 공공 서비스에 전적으로 의존합니다.
    - **위협:** 지지율이 바닥나면 생존을 위해 거리로 뛰쳐나와 걷잡을 수 없는 폭동을 일으킵니다.
    - **요구:** 복지 예산 확대, 현금 지원, 공공요금 동결
    """
}

CRISES_POOL = [
    {
        "id": 0,
        "title": "📉 글로벌 복합 금융 위기",
        "img": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?q=80&w=800",
        "desc": "미국발 금리 인상과 전쟁 리스크로 주가가 폭락하고 환율이 1,500원을 돌파했습니다. 기업들은 줄도산을 경고하고 있으며, 가계 부채는 시한폭탄처럼 째깍거리고 있습니다.",
        "options": [
            {"name": "법인세 인하 (낙수효과)", "cost": -10, "effect": [15, 5, -10, -15], 
             "detail": "기업의 세금을 깎아주어 투자를 유도합니다. 기업 숨통은 트이지만, 세수 부족으로 복지 예산이 대폭 삭감됩니다.", "reason": "자본가+15 (감세), 빈곤층-15 (복지축소)"},
            {"name": "재난지원금 살포", "cost": -30, "effect": [-15, 5, 10, 20], 
             "detail": "국채를 발행해 현금을 풉니다. 내수는 방어하지만, 물가 상승과 국가 부채 급증으로 경제 펀더멘털이 훼손됩니다.", "reason": "빈곤층+20 (현금), 자본가-15 (인플레)"},
            {"name": "고금리 긴축 (구조조정)", "cost": +10, "effect": [5, -20, -10, -5], 
             "detail": "허리띠를 졸라매어 물가를 잡습니다. 국가 신용은 지키지만, 이자 폭탄을 맞은 중산층과 자영업자가 붕괴합니다.", "reason": "자본가+5 (자산방어), 중산층-20 (이자폭탄)"}
        ]
    },
    {
        "id": 1,
        "title": "🦠 치명적 신종 바이러스",
        "img": "https://images.unsplash.com/photo-1584036561566-baf8f5f1b144?q=80&w=800",
        "desc": "치사율 높은 전염병이 확산 중입니다. 병상은 포화 상태이며, 공포에 질린 시민들의 사재기가 이어지고 있습니다. 의료 체계 붕괴 직전입니다.",
        "options": [
            {"name": "국가 봉쇄 (Lockdown)", "cost": -10, "effect": [-5, -10, -15, 5], 
             "detail": "강력한 봉쇄로 확진자는 줄이지만, 자영업자와 일용직 노동자의 생계가 끊겨 경제 활동이 마비됩니다.", "reason": "빈곤층+5 (생명보호), 노동자-15 (실직)"},
            {"name": "위드 코로나 (경제 우선)", "cost": 0, "effect": [10, 5, 0, -25], 
             "detail": "경제가 멈추는 것은 막았으나, 의료 시스템이 붕괴됩니다. 치료비가 없는 취약계층 사망자가 급증합니다.", "reason": "자본가+10 (매출유지), 빈곤층-25 (사망)"},
            {"name": "치료제 무상 공급", "cost": -40, "effect": [-5, 5, 5, 15], 
             "detail": "천문학적인 예산을 쏟아부어 국민 생명은 지킵니다. 하지만 건보 기금 고갈로 인한 증세 논의에 상위층이 반발합니다.", "reason": "빈곤층+15 (무상치료), 국고-40 (재정타격)"}
        ]
    },
    {
        "id": 2,
        "title": "📢 광화문 100만 촛불",
        "img": "https://images.unsplash.com/photo-1563986768609-322da13575f3?q=80&w=800",
        "desc": "정부의 불통과 실정에 분노한 시민들이 광화문을 가득 메웠습니다. '대통령 퇴진' 구호가 등장했습니다. 청와대 앞까지 행진이 이어집니다.",
        "options": [
            {"name": "부자 증세 및 복지 확대", "cost": +20, "effect": [-25, -5, 10, 20], 
             "detail": "시위대의 요구를 수용해 양극화 해소 대책을 발표합니다. 서민들은 환호하지만, 자산가들은 자본을 해외로 빼돌립니다.", "reason": "빈곤층+20 (혜택), 자본가-25 (세금폭탄)"},
            {"name": "공권력 투입 (강경 진압)", "cost": -5, "effect": [15, 5, -20, -15], 
             "detail": "경찰력을 동원해 강제 해산시킵니다. 보수 지지층은 결집하지만, 과잉 진압 논란으로 중도층과 젊은 세대는 등을 돌립니다.", "reason": "자본가+15 (질서), 노동자-20 (탄압)"},
            {"name": "대국민 사과 및 내각 총사퇴", "cost": 0, "effect": [-10, 5, 5, 5], 
             "detail": "대통령이 고개를 숙이고 참모진을 전원 교체합니다. 분노는 가라앉지만, 국정 동력이 상실되어 식물 정부가 됩니다.", "reason": "자본가-10 (무능), 중산층+5 (소통)"}
        ]
    },
    {
        "id": 3,
        "title": "🤖 AI가 일자리를 습격하다",
        "img": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?q=80&w=800",
        "desc": "생성형 AI의 발전으로 사무직과 단순 노무직의 대량 해고가 시작되었습니다. '기계가 인간을 대체한다'는 공포가 사회를 덮쳤습니다.",
        "options": [
            {"name": "로봇세 도입 (기본소득)", "cost": -15, "effect": [-20, 5, 10, 10], 
             "detail": "기업에 세금을 물려 실직자에게 현금을 지급합니다. 노동자들은 안도하지만, 기업들은 '규제 감옥'이라며 반발합니다.", "reason": "자본가-20 (규제), 노동자+10 (안전망)"},
            {"name": "AI 규제 철폐 (성장)", "cost": +10, "effect": [20, 5, -15, -15], 
             "detail": "AI 강국으로 도약하며 국가 경쟁력은 폭등합니다. 하지만 구조조정 당한 수만 명의 노동자들이 빈곤층으로 전락합니다.", "reason": "자본가+20 (주가폭등), 노동자-15 (해고)"},
            {"name": "공공 근로 확대", "cost": -20, "effect": [-5, -5, 5, 10], 
             "detail": "정부가 세금으로 단기 일자리를 급조해 급한 불은 껐습니다. 하지만 질 낮은 일자리 양산이라는 비판을 받습니다.", "reason": "빈곤층+10 (생계), 국고-20 (비용)"}
        ]
    },
    {
        "id": 4,
        "title": "⚔️ 주변국 무역 보복 조치",
        "img": "https://images.unsplash.com/photo-1595246737293-27d096162332?q=80&w=800",
        "desc": "외교 갈등으로 주요 교역국이 반도체 핵심 소재 수출을 금지했습니다. 공장 가동이 멈추고 수출길이 막힐 위기입니다.",
        "options": [
            {"name": "굴욕적 협상 (실리)", "cost": 0, "effect": [10, 5, 5, -5], 
             "detail": "상대국의 요구를 들어주고 수출길을 엽니다. 경제는 살렸으나, '국격을 팔아먹었다'는 국민적 비난을 받습니다.", "reason": "자본가+10 (매출회복), 빈곤층-5 (자존심)"},
            {"name": "강경 대응 (맞불)", "cost": -10, "effect": [-15, -10, -10, -5], 
             "detail": "자존심은 지킵니다. 하지만 무역 전쟁이 장기화되면서 물가가 폭등하고 기업 실적이 악화되어 전 국민이 고통받습니다.", "reason": "자본가-15 (매출급감), 중산층-10 (물가)"},
            {"name": "소재 국산화 R&D", "cost": -30, "effect": [-5, -5, 5, 0], 
             "detail": "기술 독립을 선언합니다. 방향은 옳지만, 성과가 나오기까지 막대한 예산 출혈과 경기 침체를 감내해야 합니다.", "reason": "노동자+5 (일자리), 국고-30 (지출)"}
        ]
    },
    {
        "id": 5,
        "title": "🏭 최악의 미세먼지와 기후 재난",
        "img": "https://images.unsplash.com/photo-1579766922979-4d6cb600259d?q=80&w=800",
        "desc": "숨을 쉴 수 없는 미세먼지와 기록적인 폭우가 동시에 덮쳤습니다. 반지하 거주민이 고립되고 농작물 가격이 폭등합니다.",
        "options": [
            {"name": "탄소세 도입 (규제)", "cost": +5, "effect": [-15, -5, 5, 10], 
             "detail": "강력한 규제로 환경은 개선됩니다. 하지만 비용 부담이 커진 기업들이 고용을 줄이고, 물가가 상승합니다.", "reason": "자본가-15 (비용), 빈곤층+10 (안전)"},
            {"name": "경제 우선 (규제 완화)", "cost": 0, "effect": [15, 5, -10, -20], 
             "detail": "공장을 풀가동해 경제 지표는 방어했습니다. 그러나 기후 재난의 피해는 고스란히 빈민가의 주거 환경 파괴로 이어집니다.", "reason": "자본가+15 (이익), 빈곤층-20 (침수피해)"},
            {"name": "피해 복구 지원금", "cost": -20, "effect": [-5, 0, 0, 10], 
             "detail": "피해 입은 국민에게 현금을 지급합니다. 하지만 근본적인 원인은 해결되지 않아 매년 같은 재난이 반복될 것입니다.", "reason": "빈곤층+10 (구제), 국고-20 (지출)"}
        ]
    },
    {
        "id": 6,
        "title": "📉 합계출산율 0.5명 쇼크",
        "img": "https://images.unsplash.com/photo-1519689680058-324335c77eba?q=80&w=800",
        "desc": "국가 소멸 위기론이 대두되었습니다. 국민연금 고갈 공포가 확산되며 세대 간 갈등이 폭발 직전입니다.",
        "options": [
            {"name": "현금 지원 대폭 확대", "cost": -30, "effect": [-5, 10, 5, -5], 
             "detail": "아이 낳는 가정에 파격적인 돈을 줍니다. 하지만 재원 마련을 위해 노인 복지 예산을 깎아 노인 빈곤이 심화됩니다.", "reason": "중산층+10 (양육비), 빈곤층-5 (복지축소)"},
            {"name": "이민청 설립 (개방)", "cost": -5, "effect": [10, -10, -10, 5], 
             "detail": "외국인으로 노동력을 채워 기업은 안도합니다. 하지만 일자리 경쟁이 치열해진 노동자와 문화적 충돌을 우려하는 중산층의 반발이 거셉니다.", "reason": "자본가+10 (인력), 노동자-10 (경쟁)"},
            {"name": "연금 개혁 (고통 분담)", "cost": +10, "effect": [-5, -15, -15, -5], 
             "detail": "재정 시한폭탄은 제거했습니다. 그러나 당장 월급에서 더 많은 돈이 떼이는 직장인들의 분노가 투표 심판으로 이어집니다.", "reason": "중산층-15 (보험료), 국고+10 (재정)"}
        ]
    },
    {
        "id": 7,
        "title": "🏘️ 부동산 시장 대폭락",
        "img": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?q=80&w=800",
        "desc": "금리 인상 여파로 집값이 30% 이상 급락했습니다. 깡통 전세 피해자가 속출하고 건설사 부도 위기가 감돕니다.",
        "options": [
            {"name": "부양책 (규제 완화)", "cost": -10, "effect": [15, 5, -10, -10], 
             "detail": "다주택자 감세와 대출 완화로 집값을 방어합니다. 하지만 '부자만 살려준다'는 비판 속에 무주택 서민의 꿈은 멀어집니다.", "reason": "자본가+15 (자산방어), 노동자-10 (박탈감)"},
            {"name": "시장 자율 (방관)", "cost": 0, "effect": [-20, -20, 10, 5], 
             "detail": "거품이 꺼지며 무주택자들은 환호합니다. 하지만 자산이 증발한 상위층과 중산층의 소비가 얼어붙어 실물 경기가 침체됩니다.", "reason": "자본가-20 (폭락), 노동자+10 (내집마련)"},
            {"name": "전세 사기 피해 구제", "cost": -20, "effect": [-5, -5, 10, 15], 
             "detail": "세금으로 피해 보증금을 지원합니다. 하지만 성실 상환자들과의 형평성 논란이 일며 납세자들의 불만이 커집니다.", "reason": "빈곤층+15 (구제), 국고-20 (세금)"}
        ]
    },
    {
        "id": 8,
        "title": "🕵️ 권력형 비리 게이트",
        "img": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?q=80&w=800",
        "desc": "장관 후보자 자녀의 특혜 채용과 입시 비리가 드러났습니다. '공정'에 민감한 여론이 폭발했습니다.",
        "options": [
            {"name": "성역 없는 수사", "cost": 0, "effect": [-15, 10, 10, 0], 
             "detail": "성역 없는 수사로 지지율을 회복했습니다. 하지만 여당 내 기득권 세력이 반발하며 대통령의 당내 입지가 좁아집니다.", "reason": "중산층+10 (공정), 자본가-15 (반발)"},
            {"name": "정치 탄압 주장 (옹호)", "cost": 0, "effect": [5, -20, -20, -5], 
             "detail": "핵심 지지층은 결집시켰으나, 중도층과 청년층은 '내로남불'이라며 등을 돌렸습니다. 도덕성에 치명상을 입습니다.", "reason": "자본가+5 (결집), 중산층-20 (실망)"},
            {"name": "제도 개혁 약속 (물타기)", "cost": -10, "effect": [-5, 5, 5, 0], 
             "detail": "제도 개선을 약속하며 시선을 돌렸습니다. 근본적인 해결책이 될 수 있으나, 당장의 분노를 잠재우기엔 역부족입니다.", "reason": "중산층+5 (기대), 자본가-5 (피로)"}
        ]
    },
    {
        "id": 9,
        "title": "⚡ 에너지 위기 (유가 폭등)",
        "img": "https://images.unsplash.com/photo-1565514020125-998dc57774dc?q=80&w=800",
        "desc": "중동 전쟁으로 유가가 배럴당 150불을 넘었습니다. 난방비 폭탄에 서민들은 떨고 있고, 한전 적자는 감당 불가입니다.",
        "options": [
            {"name": "요금 현실화 (인상)", "cost": +10, "effect": [0, -10, -15, -20], 
             "detail": "공기업 부실은 막았고 국가 신용도도 지켰습니다. 하지만 관리비 고지서를 받은 국민들의 분노가 하늘을 찌릅니다.", "reason": "국고+10 (건전성), 빈곤층-20 (생존위협)"},
            {"name": "요금 동결 (적자 보전)", "cost": -30, "effect": [-5, 10, 10, 10], 
             "detail": "세금으로 요금 인상을 막아 국민 부담은 줄였습니다. 하지만 국가 부채가 급증했고, 에너지 과소비는 여전합니다.", "reason": "빈곤층+10 (안도), 국고-30 (부채)"},
            {"name": "바우처 선별 지급", "cost": -10, "effect": [0, -5, -5, 15], 
             "detail": "취약계층에게만 난방비를 지원했습니다. 지원을 못 받은 중산층과 서민들은 상대적 박탈감을 호소합니다.", "reason": "빈곤층+15 (생존), 노동자-5 (박탈감)"}
        ]
    },
    {
        "id": 10,
        "title": "💣 북한 국지적 도발",
        "img": "https://images.unsplash.com/photo-1596720426673-e4f28bc40470?q=80&w=800",
        "desc": "휴전선 인근에서 포격 도발이 발생했습니다. 금융 시장은 출렁이고 안보 불안감이 최고조에 달했습니다.",
        "options": [
            {"name": "강력 응징 (보복)", "cost": -20, "effect": [5, -5, -5, -5], 
             "detail": "단호한 대처로 보수층 결집과 안보 의지를 보여주었습니다. 하지만 전쟁 공포로 외국인 자본이 빠져나가 주가가 폭락합니다.", "reason": "자본가+5 (안보), 중산층-5 (주가하락)"},
            {"name": "대화 시도 (평화)", "cost": 0, "effect": [-15, 5, 5, 5], 
             "detail": "확전은 막았지만, '굴종적인 태도'라는 비판을 받습니다. 보수 지지층이 이탈하고 군의 사기가 저하되었습니다.", "reason": "자본가-15 (실망), 빈곤층+5 (평화)"},
            {"name": "국방비 증액", "cost": -30, "effect": [-5, -10, -15, -5], 
             "detail": "자주 국방력을 강화했습니다. 그러나 복지 예산을 국방비로 돌려쓰는 바람에 민생이 어려워졌습니다.", "reason": "노동자-15 (민생고), 국고-30 (지출)"}
        ]
    },
    {
        "id": 11,
        "title": "🚢 대형 해상 참사",
        "img": "https://images.unsplash.com/photo-1627916562099-234b63309b69?q=80&w=800",
        "desc": "대형 인명 사고 발생. 국가 안전 시스템 부재와 늦장 대응에 대한 비판이 쏟아집니다.",
        "options": [
            {"name": "전면 안전 감찰", "cost": -10, "effect": [-10, 5, 5, 5], 
             "detail": "사회 전반의 안전 시스템을 점검했습니다. 국민들은 안심하지만, 기업들은 과도한 규제라며 불만을 토로합니다.", "reason": "자본가-10 (규제), 중산층+5 (안전)"},
            {"name": "희생자 배상 및 추모", "cost": -15, "effect": [-5, 0, 0, 5], 
             "detail": "유가족을 위로하고 추모 분위기를 조성했습니다. 하지만 '언제까지 과거에 매달릴 거냐'는 피로감이 국론을 분열시킵니다.", "reason": "빈곤층+5 (위로), 자본가-5 (피로감)"},
            {"name": "실무자 처벌로 마무리", "cost": 0, "effect": [0, -10, -10, -5], 
             "detail": "실무자 몇 명을 구속하고 덮으려 했습니다. 국민들은 '진짜 책임자는 빠져나갔다'며 정부 불신이 깊어집니다.", "reason": "중산층-10 (불신), 노동자-10 (분노)"}
        ]
    },
    {
        "id": 12,
        "title": "🧬 신약 부작용 사태",
        "img": "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?q=80&w=800",
        "desc": "국가 지원 신약에서 치명적인 부작용이 발견되었습니다. 피해자들의 소송과 정부 책임론이 대두됩니다.",
        "options": [
            {"name": "허가 취소 및 배상", "cost": -20, "effect": [-10, 5, 5, 5], 
             "detail": "국민 안전을 선택해 신뢰를 회복했습니다. 하지만 바이오 산업 투자가 위축되고, 관련 기업 주가 폭락으로 투자자들이 울상입니다.", "reason": "중산층+5 (신뢰), 자본가-10 (주가하락)"},
            {"name": "인과관계 규명 우선", "cost": 0, "effect": [10, -10, -10, -5], 
             "detail": "산업 보호를 위해 시간을 끌었습니다. 기업은 안도하지만, 피해자들은 '기업 편들기'라며 울분을 토합니다.", "reason": "자본가+10 (보호), 중산층-10 (비판)"},
            {"name": "공공 의료 강화", "cost": -30, "effect": [-15, 5, 10, 15], 
             "detail": "민간 주도 개발의 한계를 인정하고 공공 의료를 확충했습니다. 의료 서비스 질은 올랐으나, 막대한 세금이 투입됩니다.", "reason": "빈곤층+15 (혜택), 자본가-15 (세금)"}
        ]
    },
    {
        "id": 13,
        "title": "🍔 프랜차이즈 갑질",
        "img": "https://images.unsplash.com/photo-1606787366850-de6330128bfc?q=80&w=800",
        "desc": "대형 본사의 갑질로 가맹점주가 사망했습니다. 경제 민주화 요구가 빗발칩니다.",
        "options": [
            {"name": "규제 3법 통과", "cost": 0, "effect": [-20, 5, 10, 10], 
             "detail": "대기업의 횡포를 막을 강력한 법안을 만들었습니다. 을(乙)들은 환호하지만, 재계는 '기업 죽이기'라며 반발합니다.", "reason": "자본가-20 (규제), 노동자+10 (보호)"},
            {"name": "자율 상생 유도", "cost": 0, "effect": [10, -5, -10, -5], 
             "detail": "기업의 자정에 맡기기로 했습니다. 시장 자유는 지켰으나, 국민들은 '기업 봐주기'라며 정부를 의심합니다.", "reason": "자본가+10 (자유), 노동자-10 (실망)"},
            {"name": "긴급 대출 지원", "cost": -15, "effect": [-5, 5, 0, 10], 
             "detail": "피해 입은 자영업자에게 돈을 빌려줍니다. 당장 폐업은 막았지만 가계 부채만 늘리는 꼴이 되었습니다.", "reason": "빈곤층+10 (생존), 국고-15 (지출)"}
        ]
    },
    {
        "id": 14,
        "title": "📉 코인 거래소 파산",
        "img": "https://images.unsplash.com/photo-1621504450168-38f647319936?q=80&w=800",
        "desc": "국내 1위 코인 거래소가 먹튀 파산했습니다. 2030 세대의 자산이 증발하고 자살 시도가 잇따릅니다.",
        "options": [
            {"name": "투자자 손실 보전", "cost": -25, "effect": [-10, -10, 15, -5], 
             "detail": "세금으로 피해를 보전해줍니다. 청년 파산은 막았으나, '도박 빚을 갚아주냐'는 성실 납세자들의 분노가 폭발했습니다.", "reason": "노동자+15 (구제), 중산층-10 (분노)"},
            {"name": "투자자 자기 책임", "cost": 0, "effect": [5, 5, -20, -10], 
             "detail": "투기 수요에 경종을 울렸습니다. 하지만 전 재산을 잃은 청년층이 대거 신용불량자로 전락하며 사회적 활력이 떨어집니다.", "reason": "중산층+5 (원칙), 노동자-20 (파산)"},
            {"name": "가상자산 규제 강화", "cost": -5, "effect": [-5, 0, -5, 0], 
             "detail": "뒤늦게 규제 장벽을 세웠습니다. 시장은 건전해졌지만, '소 잃고 외양간 고치기'라는 비판과 함께 산업 위축을 가져왔습니다.", "reason": "자본가-5 (규제), 노동자-5 (뒷북)"}
        ]
    }
]

# -----------------------------------------------------------------------------
# [메인 로직]
# -----------------------------------------------------------------------------
# 배경음악/사진 렌더링
render_bgm()
render_background()

# 상태 초기화
if 'turn' not in st.session_state:
    st.session_state.turn = 1
    st.session_state.stats = {k: 50 for k in ARCHS}
    st.session_state.budget = 100
    st.session_state.game_over = False
    st.session_state.fail_msg = ""
    st.session_state.logs = []
    st.session_state.player_name = "성함을 입력해주세요"
    
    deck = list(range(len(CRISES_POOL)))
    random.shuffle(deck)
    st.session_state.event_deck = deck
    st.session_state.current_crisis = CRISES_POOL[st.session_state.event_deck.pop()]

# 턴 넘기기
def next_turn(idx):
    opt = st.session_state.current_crisis['options'][idx]
    st.session_state.budget += opt['cost']
    for i, a in enumerate(ARCHS):
        st.session_state.stats[a] = max(0, min(100, st.session_state.stats[a] + opt['effect'][i]))
    
    st.session_state.logs.append(f"Turn {st.session_state.turn}: {opt['name']} 선택")
    
    # [수정] 게임 오버 로직 고도화 (누구 때문에 망했는지 확인)
    if st.session_state.budget < 0:
        st.session_state.game_over = True
        st.session_state.fail_msg = "💸 국가 부도 선언 (국고 고갈)"
    elif st.session_state.stats["자본가"] <= 0:
        st.session_state.game_over = True
        st.session_state.fail_msg = "📉 자본가들의 대규모 자본 이탈로 경제 붕괴"
    elif st.session_state.stats["중산층"] <= 0:
        st.session_state.game_over = True
        st.session_state.fail_msg = "🕯️ 중산층의 조세 저항 및 대통령 탄핵 시위"
    elif st.session_state.stats["노동자"] <= 0:
        st.session_state.game_over = True
        st.session_state.fail_msg = "✊ 노동자 총파업으로 국가 기능 마비"
    elif st.session_state.stats["빈곤층"] <= 0:
        st.session_state.game_over = True
        st.session_state.fail_msg = "🔥 빈곤층의 생존권 투쟁 및 대규모 폭동"
    elif st.session_state.turn >= 10:
        st.session_state.game_over = True
        st.session_state.fail_msg = "🎉 임기 5년 만료"
    else:
        st.session_state.turn += 1
        st.session_state.current_crisis = CRISES_POOL[st.session_state.event_deck.pop()]

# UI: 명패 및 상태바
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

st.title("🏛️ 미스터 프레지던트")

# 사이드바
with st.sidebar:
    st.header("1. 대통령 취임")
    # 콜백 함수로 엔터 치자마자 업데이트
    st.text_input("성함 입력 (엔터치면 반영):", key="temp_name", on_change=update_name)
    
    # 초기값 설정
    if 'temp_name' not in st.session_state:
        st.session_state.temp_name = st.session_state.player_name

    st.markdown("---")
    st.header("ℹ️ 계층 가이드")
    with st.expander("❓ 계층별 핵심 이익 보기"):
        for k, v in ARCH_DESC.items():
            st.markdown(f"{v}")
            st.markdown("---")

# HUD (진행 상황 추가)
cols = st.columns(5)
cols[0].metric("국고", f"{st.session_state.budget}조")
for i, a in enumerate(ARCHS):
    # 지지율이라고 명시
    cols[i+1].metric(f"{a} 지지율", f"{st.session_state.stats[a]}%")

# [수정] 진행바에 텍스트 추가 (남은 안건 수)
if not st.session_state.game_over:
    st.write(f"### 🗓️ 임기 {st.session_state.turn}년차 / 총 10년 (남은 안건: {11 - st.session_state.turn}개)")
    st.progress(min(1.0, (st.session_state.turn - 1) / 10))

st.markdown("---")

# 게임 화면
if st.session_state.game_over:
    if "성공" in st.session_state.fail_msg or "만료" in st.session_state.fail_msg:
        st.balloons()
        st.success(f"🏆 {st.session_state.fail_msg}")
        
        avg = sum(st.session_state.stats.values()) / 4
        budget = st.session_state.budget
        
        st.markdown(f"### 📊 최종 성적: 평균 지지율 {avg:.1f}% / 국고 {budget}조")
        
        # [엔딩 분기: 뉴스 헤드라인 깔끔하게 정리 (줄바꿈 수정)]
        st.subheader("📰 [호외] 임기 종료 특별 보도")
        
        if avg >= 80 and budget >= 80:
            st.success(f"### 🌟 역사상 가장 위대한 지도자, {st.session_state.player_name} 대통령 퇴임\n\n지지율과 경제 두 마리 토끼를 모두 잡은 '전설의 성군'으로 기록될 것")
        elif avg >= 60:
            st.success(f"### ✅ 성공적인 국정 운영, 박수칠 때 떠나는 {st.session_state.player_name} 대통령\n\n숱한 위기 속에서도 대한민국을 안정적으로 이끌었다는 평가")
        elif budget < 20:
            st.warning(f"### 💸 '인기는 얻었으나 곳간은 비었다'... 포퓰리즘 논란 속 퇴임\n\n차기 정부에 막대한 재정 부담을 넘기게 되어... 국가 신용등급 우려")
        elif avg < 30:
            st.error(f"### 💀 역대 최저 지지율... {st.session_state.player_name} 대통령의 쓸쓸한 뒷모습\n\n국론 분열과 정책 실패로 얼룩진 5년... '식물 정부' 오명 남겨")
        else:
            st.info(f"### ⚖️ '공과 과' 뚜렷... {st.session_state.player_name} 정부 5년의 막을 내리다\n\n위기 관리 능력은 돋보였으나, 계층 간 갈등 해소는 과제로 남아")

        # 지지층 분석
        sorted_stats = sorted(st.session_state.stats.items(), key=lambda x: x[1])
        best_group = sorted_stats[-1]
        worst_group = sorted_stats[0]
        
        st.markdown(f"""
        ---
        **🔍 계층별 지지 성향 분석**
        * ❤️ **콘크리트 지지층:** {best_group[0]} ({best_group[1]}%)
        * 💔 **최대 비토층:** {worst_group[0]} ({worst_group[1]}%)
        """)
        
    else:
        st.error(f"💀 GAME OVER: {st.session_state.fail_msg}")
        # 게임오버 상세 사유
        reason = ""
        if "부도" in st.session_state.fail_msg:
            reason = "국가 재정이 바닥나 IMF 구제금융을 신청하게 되었습니다."
        elif "자본" in st.session_state.fail_msg:
            reason = "외국인 투자자가 모두 떠나고 증시가 폭락했습니다."
        elif "중산층" in st.session_state.fail_msg:
            reason = "광화문에 100만 명이 모여 대통령 탄핵을 외치고 있습니다."
        elif "노동자" in st.session_state.fail_msg:
            reason = "전국적인 총파업으로 전기, 수도, 교통이 모두 끊겼습니다."
        elif "빈곤층" in st.session_state.fail_msg:
            reason = "생존권을 요구하는 격렬한 시위가 폭동으로 번졌습니다."
        
        st.markdown(f"**{reason}**")
    
    if st.button("🔄 다시 하기"):
        st.session_state.clear()
        st.rerun()
        
    with st.expander("📜 지난 기록 보기"):
        for log in st.session_state.logs:
            st.write(log)

else:
    c = st.session_state.current_crisis
    st.error(f"🚨 [속보] {c['title']}")
    
    # [수정] 이미지 표시 (로컬 파일 우선, 없으면 웹 URL, 둘 다 없으면 표시 안함)
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
