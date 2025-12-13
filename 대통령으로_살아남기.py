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

# [데이터] 통치 스타일 (공유용 카드 + 실존 인물 통합)
RULING_STYLES = {
    "진보": {
        "title": "따뜻한 낭만주의자",
        "emoji": "🌷",
        "color": "#FFD700",
        "keywords": ["#원칙과 상식", "#약자와의 동행", "#진보"],
        "desc": "당신은 숫자가 떨어져도 사람을 버리지 못하는 낭만파입니다.<br>기득권의 반발을 사더라도, 소외된 이웃을 위한 혁명적인 정책을 밀어붙입니다.<br>때로는 '현실 감각이 없다'는 비판을 듣지만, 열성적인 팬덤을 거느립니다.",
        "quote": "국가의 존재 이유는 숫자가 아니라 사람입니다.",
        "models": [{"name": "노무현", "id": "roh", "img": "https://upload.wikimedia.org/wikipedia/commons/f/f3/Roh_Moo-hyun_Presidential_Portrait.jpg"}, {"name": "김대중", "id": "dj", "img": "https://upload.wikimedia.org/wikipedia/commons/e/ee/Kim_Dae-jung_Official_Portrait.jpg"}]
    },
    "중도진보": {
        "title": "줄타기의 귀재",
        "emoji": "⚖️",
        "color": "#4B89DC",
        "keywords": ["#소통의 달인", "#공정사회", "#중도진보"],
        "desc": "당신은 '통합'과 '공정'을 최우선 가치로 두는 리더입니다..<br>격렬한 싸움보다는 대화와 타협을 선호하며, 대중적인 인기를 관리하는 능력이 탁월합니다.<br>'좋은 게 좋은 거다'며 중립 행보를 하다 우유부단하다는 비판을 듣기도 합니다.",
        "quote": "특권과 반칙이 없는 세상, 억울한 사람이 없는 나라를 만들겠습니다.",
        "models": [{"name": "이재명", "id": "lee", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/Lee_Jae-myung_%28cropped%29.jpg/440px-Lee_Jae-myung_%28cropped%29.jpg"},{"name": "문재인", "id": "moon", "img": "https://upload.wikimedia.org/wikipedia/commons/3/36/Moon_Jae-in_presidential_portrait.jpg"}]
    },
    "중도보수": {
        "title": "AI 같은 실용주의자",
        "emoji": "💻",
        "color": "#A020F0",
        "keywords": ["#효율 끝판왕", "#능력지상주의", "#중도보수"],
        "desc": "탁상공론식 이념논쟁보단 '데이터'와 '결과'를 숭배합니다.<br>비효율적인 관습을 타파하고 스마트한 국가를 꿈꾸지만,<br>가끔은 너무 차가워서 '로봇 아니냐'는 의심을 받기도 합니다.",
        "quote": "그 정책, 데이터로 증명할 수 있습니까?",
        "models": [{"name": "이준석", "id": "jun", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Lee_Jun-seok_%28cropped%29.jpg/440px-Lee_Jun-seok_%28cropped%29.jpg"}, {"name": "안철수", "id": "ahn", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Ahn_Cheol-soo_portrait.jpg/440px-Ahn_Cheol-soo_portrait.jpg"}]
    },
    "보수": {
        "title": "인간 불도저",
        "emoji": "🚜",
        "color": "#E03E3E",
        "keywords": ["#강한 대한민국", "#자유시장경제", "#보수"],
        "desc": "당신은 목표를 정하면 뒤도 안 돌아보고 돌진하는 불도저입니다.<br>시장의 자유와 튼튼한 안보를 최우선으로 여기며, 타협보다는 '법과 원칙'을 엄격하게 적용합니다.<br>강력한 추진력에 환호하는 지지층과, 소통 부재를 우려하는 목소리가 공존합니다.", # 수정됨
        "quote": "자유와 원칙을 무너뜨리는 세력과는 타협하지 않습니다!",
        "models": [{"name": "윤석열", "id": "yoon", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Yoon_Suk-yeol_in_May_2022.jpg/440px-Yoon_Suk-yeol_in_May_2022.jpg"}, {"name": "김문수", "id": "kim", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Kim_Moon-soo_in_October_2024.png/440px-Kim_Moon-soo_in_October_2024.png"}]
    }
}

CRISES_POOL = {
    "초기": [
        {"id": 13, "title": "🍔 프랜차이즈 갑질 파동", "img": "https://images.unsplash.com/photo-1550547660-d9450f859349", "desc": "🚨속보\n\n대형 본사의 갑질로 가맹점주가 사망하는 비극이 발생했습니다. '을의 눈물'에 공감한 국민들의 분노가 들끓고 있으며, 강력한 경제 민주화를 요구하는 목소리가 높습니다.", "options": [{"name": "규제 3법 통과", "cost": 0, "effect": [-20, 5, 10, 10], "detail": "대기업의 횡포를 막을 강력한 법안을 만듭니다. 을(乙)들은 환호하지만, 재계는 '기업 죽이기'라며 투자 축소를 경고합니다.", "reason": "자본가-20 (규제), 노동자+10 (보호)"}, {"name": "자율 상생 유도", "cost": 0, "effect": [10, -5, -10, -5], "detail": "기업의 자정에 맡기기로 했습니다. 시장 자유는 지켰으나, 국민들은 '기업 봐주기'라며 정부가 로비에 넘어갔다고 의심합니다.", "reason": "자본가+10 (자유), 노동자-10 (실망)"}, {"name": "긴급 대출 지원", "cost": -15, "effect": [-5, 5, 0, 10], "detail": "피해 입은 자영업자에게 돈을 빌려줍니다. 당장 폐업은 막았지만 근본적인 구조는 그대로이며, 가계 부채만 늘리는 꼴이 되었습니다.", "reason": "빈곤층+10 (생존), 국고-15 (지출)"}]},
        {"id": 14, "title": "📉 코인 거래소 먹튀", "img": "https://images.unsplash.com/photo-1621504450168-38f647319936", "desc": "🚨속보\n\n국내 1위 코인 거래소가 먹튀 파산했습니다. 2030 세대의 자산이 증발하고 자살 시도가 잇따르며 사회적 혼란이 가중되고 있습니다.", "options": [{"name": "투자자 손실 보전", "cost": -25, "effect": [-10, -10, 15, -5], "detail": "세금으로 피해를 보전해줍니다. 청년 파산은 막았으나, '도박 빚을 갚아주냐'는 성실 납세자들의 분노가 폭발했습니다.", "reason": "노동자+15 (구제), 중산층-10 (분노)"}, {"name": "책임 원칙", "cost": 0, "effect": [5, 5, -20, -10], "detail": "투기 수요에 경종을 울렸습니다. 하지만 전 재산을 잃은 청년층이 대거 신용불량자로 전락하며 사회적 활력이 급격히 떨어집니다.", "reason": "중산층+5 (원칙), 노동자-20 (파산)"}, {"name": "가상자산 규제 강화", "cost": -5, "effect": [-5, 0, -5, 0], "detail": "뒤늦게 규제 장벽을 세웠습니다. 시장은 건전해졌지만, '소 잃고 외양간 고치기'라는 비판과 함께 블록체인 산업 위축을 가져왔습니다.", "reason": "자본가-5 (규제), 노동자-5 (뒷북)"}]},
        {"id": 3, "title": "🤖 AI 일자리 습격", "img": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e", "desc": "🚨속보\n\n생성형 AI의 발전으로 사무직과 단순 노무직의 대량 해고가 시작되었습니다. '기계가 인간을 대체한다'는 공포가 사회를 덮쳤습니다.", "options": [{"name": "로봇세 도입 (기본소득)", "cost": -15, "effect": [-20, 5, 10, 10], "detail": "기업에 세금을 물려 실직자에게 현금을 지급합니다. 노동자들은 안도하지만, 기업들은 '혁신을 가로막는 규제 감옥'이라며 반발합니다.", "reason": "자본가-20 (규제), 노동자+10 (안전망)"}, {"name": "AI 규제 철폐 (성장)", "cost": +10, "effect": [20, 5, -15, -15], "detail": "AI 강국으로 도약하며 국가 경쟁력은 폭등합니다. 하지만 구조조정 당한 수만 명의 노동자들이 거리로 나앉아 빈곤층으로 전락합니다.", "reason": "자본가+20 (주가폭등), 노동자-15 (해고)"}, {"name": "공공 근로 확대", "cost": -20, "effect": [-5, -5, 5, 10], "detail": "정부가 세금으로 단기 일자리를 급조해 급한 불은 껐습니다. 하지만 '세금 낭비', '질 낮은 일자리'라는 비판을 받습니다.", "reason": "빈곤층+10 (생계), 국고-20 (비용)"}]},
        {"id": 12, "title": "🧬 신약 부작용 사태", "img": "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69", "desc": "🚨속보\n\n국가 지원 신약에서 치명적인 부작용이 발견되었습니다. 피해자들의 소송과 정부 책임론이 대두되며 바이오 산업이 흔들립니다.", "options": [{"name": "허가 취소 및 배상", "cost": -20, "effect": [-10, 5, 5, 5], "detail": "국민 안전을 선택해 신뢰를 회복했습니다. 하지만 바이오 산업 투자가 위축되고, 관련 기업 주가 폭락으로 개미 투자자들이 울상입니다.", "reason": "중산층+5 (신뢰), 자본가-10 (주가하락)"}, {"name": "인과관계 규명 우선", "cost": 0, "effect": [10, -10, -10, -5], "detail": "산업 보호를 위해 시간을 끌었습니다. 기업은 안도하지만, 피해자들은 '기업 편들기'라며 울분을 토하고 정부의 생명 경시 풍조가 비판받습니다.", "reason": "자본가+10 (보호), 중산층-10 (비판)"}, {"name": "공공 의료 강화", "cost": -30, "effect": [-15, 5, 10, 15], "detail": "민간 주도 개발의 한계를 인정하고 공공 의료를 확충했습니다. 의료 서비스 질은 올랐으나, 막대한 세금이 투입되어 고소득층 저항이 심합니다.", "reason": "빈곤층+15 (혜택), 자본가-15 (세금)"}]}
    ],
    "중기": [
        {"id": 7, "title": "🏘️ 부동산 시장 대폭락", "img": "https://images.unsplash.com/photo-1560518883-ce09059eeffa", "desc": "🚨속보\n\n금리 인상 여파로 집값이 30% 이상 급락했습니다. 깡통 전세 피해자가 속출하고 건설사 부도 위기가 감돕니다.", "options": [{"name": "부양책 (규제 완화)", "cost": -10, "effect": [15, 5, -10, -10], "detail": "다주택자 감세와 대출 완화로 집값 방어에 성공해 자산가들은 안도합니다. 하지만 '부자만 살려준다'는 비판 속에 무주택 서민의 꿈은 멀어집니다.", "reason": "자본가+15 (자산방어), 노동자-10 (박탈감)"}, {"name": "시장 자율 (방관)", "cost": 0, "effect": [-20, -20, 10, 5], "detail": "거품이 꺼지며 무주택자들은 환호합니다. 하지만 자산이 증발한 상위층과 중산층의 소비가 얼어붙어 실물 경기가 깊은 침체에 빠집니다.", "reason": "자본가-20 (폭락), 노동자+10 (내집마련)"}, {"name": "전세 사기 피해 구제", "cost": -20, "effect": [-5, -5, 10, 15], "detail": "세금으로 피해 보증금을 지원해 서민들의 눈물을 닦아주었습니다. 하지만 성실 상환자들과의 형평성 논란이 일며 납세자들의 불만이 커집니다.", "reason": "빈곤층+15 (구제), 국고-20 (세금)"}]},
        {"id": 9, "title": "⚡ 에너지 위기", "img": "https://images.unsplash.com/photo-1565514020125-998dc57774dc", "desc": "🚨속보\n\n중동 전쟁으로 유가가 배럴당 150불을 넘었습니다. 난방비 폭탄에 서민들은 떨고 있고, 한전 적자는 감당 불가입니다.", "options": [{"name": "요금 현실화 (인상)", "cost": +10, "effect": [0, -10, -15, -20], "detail": "공기업 부실은 막았고 국가 신용도도 지켰습니다. 하지만 관리비 고지서를 받은 국민들의 분노가 하늘을 찌르고, 취약계층은 냉골에서 잡니다.", "reason": "국고+10 (건전성), 빈곤층-20 (생존위협)"}, {"name": "요금 동결 (적자 보전)", "cost": -30, "effect": [-5, 10, 10, 10], "detail": "세금으로 요금 인상을 막아 국민 부담은 줄였습니다. 하지만 국가 부채가 급증했고, 에너지 과소비는 여전해 미봉책이라는 비판을 받습니다.", "reason": "빈곤층+10 (안도), 국고-30 (부채)"}, {"name": "바우처 선별 지급", "cost": -10, "effect": [0, -5, -5, 15], "detail": "취약계층에게만 난방비를 지원했습니다. 지원을 못 받은 중산층과 서민들은 '나도 힘든데 왜 안 주냐'며 상대적 박탈감을 호소합니다.", "reason": "빈곤층+15 (생존), 노동자-5 (박탈감)"}]},
        {"id": 4, "title": "⚔️ 무역 보복 조치", "img": "https://images.unsplash.com/photo-1595246737293-27d096162332", "desc": "🚨속보\n\n외교 갈등으로 주요 교역국이 핵심 소재 수출을 금지했습니다. 공장 가동이 멈추고 수출길이 막힐 위기입니다.", "options": [{"name": "굴욕적 협상 (실리)", "cost": 0, "effect": [10, 5, 5, -5], "detail": "상대국의 요구를 들어주고 수출길을 엽니다. 경제는 살렸으나, '국격을 팔아먹었다'는 국민적 비난과 자존심의 상처는 깊습니다.", "reason": "자본가+10 (매출회복), 빈곤층-5 (자존심)"}, {"name": "강경 대응 (맞불)", "cost": -10, "effect": [-15, -10, -10, -5], "detail": "자주 국가의 자존심은 지킵니다. 하지만 무역 전쟁이 장기화되면서 물가가 폭등하고 기업 실적이 악화되어 전 국민이 고통받습니다.", "reason": "자본가-15 (매출급감), 중산층-10 (물가)"}, {"name": "소재 국산화 R&D", "cost": -30, "effect": [-5, -5, 5, 0], "detail": "장기적인 기술 독립을 선언합니다. 방향은 옳지만, 당장의 성과가 나오기까지 막대한 예산 출혈과 경기 침체를 감내해야 합니다.", "reason": "노동자+5 (일자리), 국고-30 (지출)"}]},
        {"id": 5, "title": "🏭 기후 재난", "img": "https://images.unsplash.com/photo-1579766922979-4d6cb600259d", "desc": "🚨속보\n\n숨을 쉴 수 없는 미세먼지와 기록적인 폭우가 동시에 덮쳤습니다. 반지하 거주민이 고립되고 농작물 가격이 폭등합니다.", "options": [{"name": "탄소세 도입", "cost": +5, "effect": [-15, -5, 5, 10], "detail": "강력한 규제로 환경은 개선되었고 세수도 늘었습니다. 하지만 비용 부담이 커진 기업들이 고용을 줄였고, 물가 상승으로 중산층의 삶이 팍팍해졌습니다.", "reason": "자본가-15 (비용), 빈곤층+10 (안전)"}, {"name": "경제 우선", "cost": 0, "effect": [15, 5, -10, -20], "detail": "공장을 풀가동해 경제 지표는 방어했습니다. 그러나 기후 재난의 피해는 고스란히 취약계층에게 집중되어, 빈민가의 주거 환경이 파괴되었습니다.", "reason": "자본가+15 (이익), 빈곤층-20 (침수피해)"}, {"name": "피해 복구 지원금", "cost": -20, "effect": [-5, 0, 0, 10], "detail": "피해 입은 국민에게 현금을 지급해 원성을 달랬습니다. 하지만 근본적인 원인은 해결되지 않아 매년 같은 재난이 반복될 것이며 재정만 축납니다.", "reason": "빈곤층+10 (구제), 국고-20 (지출)"}]},
        {"id": 6, "title": "📉 합계출산율 0.5명", "img": "https://images.unsplash.com/photo-1519689680058-324335c77eba", "desc": "🚨속보\n\n국가 소멸 위기론이 대두되었습니다. 국민연금 고갈 공포가 확산되며 세대 간 갈등이 폭발 직전입니다.", "options": [{"name": "현금 지원 확대", "cost": -30, "effect": [-5, 10, 5, -5], "detail": "아이 낳는 가정에 파격적인 돈을 주어 중산층은 환호합니다. 하지만 재원 마련을 위해 노인 복지 예산을 깎으면서 취약계층 노인들은 생존 위기입니다.", "reason": "중산층+10 (양육비), 빈곤층-5 (복지축소)"}, {"name": "이민청 설립", "cost": -5, "effect": [10, -10, -10, 5], "detail": "노동력 부족을 외국인으로 채워 기업은 안도합니다. 하지만 일자리 경쟁이 치열해진 노동자와 문화적 충돌을 우려하는 중산층의 반발이 거셉니다.", "reason": "자본가+10 (인력), 노동자-10 (경쟁)"}, {"name": "연금 개혁", "cost": +10, "effect": [-5, -15, -15, -5], "detail": "재정 시한폭탄은 제거했습니다. 그러나 당장 월급에서 더 많은 돈이 떼이는 직장인들의 분노가 투표 심판으로 이어질 기세입니다.", "reason": "중산층-15 (보험료), 국고+10 (재정)"}]}
    ],
    "말기": [
        {"id": 0, "title": "📉 글로벌 복합 금융 위기", "img": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3", "desc": "🚨속보\n\n미국발 금리 인상과 전쟁 리스크로 주가가 폭락하고 환율이 1,500원을 돌파했습니다. 기업들은 줄도산을 경고하고 있으며, 가계 부채는 시한폭탄입니다.", "options": [{"name": "법인세 인하", "cost": -10, "effect": [15, 5, -10, -15], "detail": "기업의 세금을 깎아주어 투자를 유도합니다. 기업 숨통은 트이지만, 세수 부족으로 복지 예산이 대폭 삭감되어 빈곤층은 타격을 입습니다.", "reason": "자본가+15 (감세), 빈곤층-15 (복지축소)"}, {"name": "재난지원금 살포", "cost": -30, "effect": [-15, 5, 10, 20], "detail": "국채를 발행해 현금을 풉니다. 내수는 방어하지만, 물가 상승과 국가 부채 급증으로 경제 펀더멘털이 훼손됩니다.", "reason": "빈곤층+20 (현금), 자본가-15 (인플레)"}, {"name": "고금리 긴축", "cost": +10, "effect": [5, -20, -10, -5], "detail": "허리띠를 졸라매어 물가를 잡습니다. 국가 신용은 지키지만, 이자 폭탄을 맞은 '영끌' 중산층과 자영업자들이 붕괴합니다.", "reason": "자본가+5 (자산방어), 중산층-20 (이자폭탄)"}]},
        {"id": 2, "title": "📢 광화문 100만 촛불", "img": "https://images.unsplash.com/photo-1563986768609-322da13575f3", "desc": "🚨속보\n\n정부의 불통과 실정에 분노한 시민들이 광화문을 가득 메웠습니다. '대통령 퇴진' 구호가 등장했습니다.", "options": [{"name": "증세 및 복지", "cost": +20, "effect": [-25, -5, 10, 20], "detail": "시위대의 요구를 수용해 양극화 해소 대책을 발표합니다. 서민들은 환호하지만, 징벌적 과세에 분노한 자산가들은 자본을 해외로 빼돌립니다.", "reason": "빈곤층+20 (혜택), 자본가-25 (세금폭탄)"}, {"name": "공권력 투입", "cost": -5, "effect": [15, 5, -20, -15], "detail": "경찰력을 동원해 강제 해산시킵니다. 보수 지지층은 '법치 확립'이라며 결집하지만, 과잉 진압 논란으로 중도층과 젊은 세대는 등을 돌립니다.", "reason": "자본가+15 (질서), 노동자-20 (탄압)"}, {"name": "대국민 사과", "cost": 0, "effect": [-10, 5, 5, 5], "detail": "대통령이 고개를 숙이고 참모진을 전원 교체합니다. 분노는 가라앉지만, 국정 동력이 상실되어 아무것도 할 수 없는 '식물 정부'가 됩니다.", "reason": "자본가-10 (무능), 중산층+5 (소통)"}]},
        {"id": 10, "title": "💣 북한 국지적 도발", "img": "https://images.unsplash.com/photo-1554223249-1755a5b512c8", "desc": "🚨속보\n\n휴전선 포격 도발. 금융 시장 출렁, 안보 불안 최고조.", "options": [{"name": "강력 응징", "cost": -20, "effect": [5, -5, -5, -5], "detail": "단호한 대처로 보수층 결집과 안보 의지를 보여주었습니다. 하지만 전쟁 공포로 외국인 자본이 빠져나가고 주가가 폭락해 경제가 휘청입니다.", "reason": "자본가+5 (안보), 중산층-5 (주가하락)"}, {"name": "대화 시도", "cost": 0, "effect": [-15, 5, 5, 5], "detail": "확전은 막았지만, '굴종적인 태도'라는 비판을 받습니다. 보수 지지층이 이탈하고 군의 사기가 저하되었습니다.", "reason": "자본가-15 (실망), 빈곤층+5 (평화)"}, {"name": "국방비 증액", "cost": -30, "effect": [-5, -10, -15, -5], "detail": "자주 국방력을 강화했습니다. 그러나 복지 예산을 국방비로 돌려쓰는 바람에 민생이 어려워졌고, 청년들의 징병 부담만 커졌습니다.", "reason": "노동자-15 (민생고), 국고-30 (지출)"}]},
        {"id": 8, "title": "🕵️ 권력형 비리 게이트", "img": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f", "desc": "🚨속보\n\n측근 비리 발각. '공정'에 민감한 여론 폭발.", "options": [{"name": "성역 없는 수사", "cost": 0, "effect": [-15, 10, 10, 0], "detail": "성역 없는 수사로 지지율을 회복했습니다. 하지만 여당 내 기득권 세력이 반발하며 대통령의 당내 입지가 좁아지고 국정 운영이 외로워집니다.", "reason": "중산층+10 (공정), 자본가-15 (반발)"}, {"name": "정치 탄압 주장", "cost": 0, "effect": [5, -20, -20, -5], "detail": "핵심 지지층은 결집시켰으나, 중도층과 청년층은 '내로남불'이라며 등을 돌렸습니다. 정권의 도덕성이 바닥에 떨어졌습니다.", "reason": "자본가+5 (결집), 중산층-20 (실망)"}, {"name": "제도 개혁 약속", "cost": -10, "effect": [-5, 5, 5, 0], "detail": "제도 개선을 약속하며 시선을 돌렸습니다. 근본적인 해결책이 될 수 있으나, 당장 책임자 처벌을 원했던 여론을 잠재우기엔 역부족입니다.", "reason": "중산층+5 (기대), 자본가-5 (피로)"}]},
        {"id": 1, "title": "🦠 치명적 신종 바이러스", "img": "https://images.unsplash.com/photo-1584036561566-baf8f5f1b144", "desc": "🚨속보\n\n치사율 높은 전염병이 확산 중입니다. 의료 붕괴 직전.", "options": [{"name": "국가 봉쇄", "cost": -10, "effect": [-5, -10, -15, 5], "detail": "강력한 봉쇄로 확진자는 줄이지만, 자영업자와 일용직 노동자의 생계가 끊깁니다. 경제 활동 마비로 인한 피해가 눈덩이처럼 불어납니다.", "reason": "빈곤층+5 (생명보호), 노동자-15 (실직)"}, {"name": "위드 코로나", "cost": 0, "effect": [10, 5, 0, -25], "detail": "경제가 멈추는 것은 막았으나, 의료 시스템이 붕괴됩니다. 치료비가 없거나 면역력이 약한 취약계층 사망자가 급증하며 '각자도생' 사회가 됩니다.", "reason": "자본가+10 (매출유지), 빈곤층-25 (사망)"}, {"name": "치료제 무상", "cost": -40, "effect": [-5, 5, 5, 15], "detail": "천문학적인 예산을 쏟아부어 국민 생명은 지킵니다. 하지만 건강보험 기금이 고갈 위기에 처하고, 이를 메꾸기 위한 증세 논의에 상위층이 반발합니다.", "reason": "빈곤층+15 (무상치료), 국고-40 (재정타격)"}]}
    ]
}

FILE_BGM = "bgm.mp3"
FILE_BG = "background.jpg"
FILE_EMBLEM = "emblem.jpg"
FILE_RANKING = "ranking.csv"

ARCHS = ["자본가", "중산층", "노동자", "빈곤층"]

# =============================================================================
# [2] 핵심 기능 함수 (순서 중요: get_base64_file이 맨 위로 와야 함)
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
    # 위에서 정의한 get_base64_file을 여기서 사용합니다.
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
    return '<div style="font-size: 80px; text-align:center; margin-bottom: 10px;">🇰🇷</div>'

def update_name():
    st.session_state.player_name = st.session_state.temp_name

def get_crisis_image(idx, default_url):
    local_filename = f"crisis_{idx}.jpg"
    if os.path.exists(local_filename):
        return local_filename
    return default_url

def get_model_image(model_id, default_url):
    local_filename = f"poly_{model_id}.jpg"
    if os.path.exists(local_filename):
        return local_filename
    return default_url

# =============================================================================
# [UI] 명패 및 화면 렌더링 (이 부분이 있어야 화면에 나옵니다!)
# =============================================================================

# UI 렌더링
render_bgm()
render_background()
    
# 2. 이름 오류 방지 (없으면 빈칸 처리)
if 'player_name' not in st.session_state:
    st.session_state.player_name = ""

# 이름이 없으면 '각하'라고 표시
display_name = st.session_state.player_name if st.session_state.player_name else "성함입력\n\n모바일은 좌측상단 >> 클릭"

# 3. 명패 그리기 (화면 출력)
emblem_tag = get_emblem_tag()
st.markdown(f'''
<div class="nameplate">
    {emblem_tag}
    <div style="color:#c2a042; font-weight:bold; font-size:16px; margin-bottom:5px; letter-spacing:1px;">
        대한민국 대통령
    </div>
    <div style="color:white; font-family:'serif'; font-weight:bold; font-size:32px; text-shadow: 2px 2px 4px black;">
        {display_name}
    </div>
</div>
''', unsafe_allow_html=True)
    
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

    if diff > 40: return "진보"
    elif diff > 10: return "중도진보"
    elif diff > -40 and budget >= 50: return "중도보수"
    else: return "보수"

# =============================================================================
# [3] 게임 데이터 (상세 내용 포함)
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

# [수정] 정치인 데이터 (ID 추가됨)
# [수정] 통합 데이터 (공유용 카드 정보 + 실존 인물 정보)
# [수정] 정치인 데이터 (MBTI 스타일 + 실존 인물 통합)
POLITICIAN_TYPES = {
    "진보": {
        "title": "따뜻한 낭만주의자",
        "emoji": "🌷",
        "color": "#FFD700", # 노랑
        "keywords": ["#사람이먼저다", "#원칙주의", "#개혁"],
        "desc": "당신은 숫자가 떨어져도 사람을 버리지 못하는 낭만파입니다.<br>기득권의 반발을 사더라도, 소외된 이웃을 위한 혁명적인 정책을 밀어붙입니다.<br>때로는 '현실 감각이 없다'는 비판을 듣지만, 열성적인 팬덤을 거느립니다.",
        "quote": "국고가 비어도 가오는 살아야지!",
        "models": [
            {"name": "노무현", "id": "roh", "img": "https://upload.wikimedia.org/wikipedia/commons/f/f3/Roh_Moo-hyun_Presidential_Portrait.jpg"},
            {"name": "김대중", "id": "dj", "img": "https://upload.wikimedia.org/wikipedia/commons/e/ee/Kim_Dae-jung_Official_Portrait.jpg"}
        ]
    },
    "중도진보": {
        "title": "줄타기의 귀재",
        "emoji": "⚖️",
        "color": "#4B89DC", # 파랑
        "keywords": ["#쇼통의달인", "#안정적개혁", "#평화주의"],
        "desc": "당신은 적을 만들지 않는 부드러운 카리스마의 소유자입니다.<br>격렬한 싸움보다는 대화와 타협을 선호하며, 대중적인 인기를 관리하는 능력이 탁월합니다.<br>'좋은 게 좋은 거지'라며 넘어가려다 우유부단하다는 소리를 듣기도 합니다.",
        "quote": "싸우지 말고 사이좋게 지냅시다, 네?",
        "models": [
            {"name": "문재인", "id": "moon", "img": "https://upload.wikimedia.org/wikipedia/commons/3/36/Moon_Jae-in_presidential_portrait.jpg"},
            {"name": "이재명", "id": "lee", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/Lee_Jae-myung_%28cropped%29.jpg/440px-Lee_Jae-myung_%28cropped%29.jpg"}
        ]
    },
    "중도보수": {
        "title": "AI 같은 실용주의자",
        "emoji": "💻",
        "color": "#A020F0", # 보라
        "keywords": ["#효율끝판왕", "#팩트폭격", "#능력지상주의"],
        "desc": "당신에게 이념은 중요하지 않습니다. 오직 '데이터'와 '결과'만 중요할 뿐.<br>비효율적인 관습을 타파하고 스마트한 국가를 꿈꾸지만,<br>가끔은 너무 차가워서 '로봇 아니냐'는 의심을 받기도 합니다.",
        "quote": "그 정책, 데이터로 증명할 수 있습니까?",
        "models": [
            {"name": "안철수", "id": "ahn", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Ahn_Cheol-soo_portrait.jpg/440px-Ahn_Cheol-soo_portrait.jpg"},
            {"name": "이준석", "id": "jun", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Lee_Jun-seok_%28cropped%29.jpg/440px-Lee_Jun-seok_%28cropped%29.jpg"}
        ]
    },
    "보수": {
        "title": "불도저 같은 상남자",
        "emoji": "🚜",
        "color": "#E03E3E", # 빨강
        "keywords": ["#법과원칙", "#기업프렌들리", "#강한대한민국"],
        "desc": "당신은 목표를 정하면 뒤도 안 돌아보고 돌진하는 불도저입니다.<br>시장의 자유와 튼튼한 안보를 최우선으로 여기며, 반대파의 목소리는 힘으로 제압합니다.<br>성과는 확실하지만, 피로감을 호소하는 국민들도 많습니다.",
        "quote": "나를 따르라! 불만이 있는 자는 썩 물러가라!",
        "models": [
            {"name": "윤석열", "id": "yoon", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Yoon_Suk-yeol_in_May_2022.jpg/440px-Yoon_Suk-yeol_in_May_2022.jpg"},
            {"name": "김문수", "id": "kim", "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Kim_Moon-soo_in_October_2024.png/440px-Kim_Moon-soo_in_October_2024.png"}
        ]
    }
}

# =============================================================================
# [4] 메인 로직
# =============================================================================

# 초기화
# 상태 초기화
if 'turn' not in st.session_state:
    st.session_state.turn = 1
    st.session_state.stats = {k: 50 for k in ARCHS}
    st.session_state.budget = 100
    st.session_state.game_over = False
    st.session_state.fail_msg = ""
    st.session_state.logs = []
    
    # 기본 이름 설정
    if 'player_name' not in st.session_state:
        st.session_state.player_name = "성명을 입력하세요\n\n모바일은 좌측상단 >> 클릭"
    if 'temp_name' not in st.session_state:
        st.session_state.temp_name = ""
    
    # [중복 방지 핵심] 시기별로 카드를 미리 섞어서 덱(Deck)을 만듭니다.
    # 이렇게 하면 뽑을 때마다 카드가 줄어들어 중복이 안 나옵니다.
    st.session_state.decks = {
        "초기": random.sample(CRISES_POOL["초기"], len(CRISES_POOL["초기"])),
        "중기": random.sample(CRISES_POOL["중기"], len(CRISES_POOL["중기"])),
        "말기": random.sample(CRISES_POOL["말기"], len(CRISES_POOL["말기"]))
    }
    
    # 첫 번째 이벤트 뽑기 (초기 덱에서 하나 꺼냄)
    st.session_state.current_crisis = st.session_state.decks["초기"].pop()

def restart():
    st.session_state.clear()
    st.rerun()

# 턴 넘기기
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
        
        # 상세 실패 사유 설정
        if st.session_state.stats["자본가"] <= 0:
            st.session_state.fail_msg = "📉 자본가들의 대규모 자본 이탈로 경제 붕괴"
        elif st.session_state.stats["중산층"] <= 0:
            st.session_state.fail_msg = "🕯️ 중산층의 조세 저항 및 대통령 탄핵 시위"
        elif st.session_state.stats["노동자"] <= 0:
            st.session_state.fail_msg = "✊ 노동자 총파업으로 국가 기능 마비"
        elif st.session_state.stats["빈곤층"] <= 0:
            st.session_state.fail_msg = "🔥 빈곤층의 생존권 투쟁 및 대규모 폭동"
        else:
            st.session_state.fail_msg = "🔥 대규모 폭동 발생"

    elif st.session_state.turn >= 10:
        st.session_state.game_over = True
        st.session_state.fail_msg = "🎉 임기 5년 만료"
    else:
        st.session_state.turn += 1
        
        # [수정] 시기에 맞는 덱에서 카드 뽑기 (pop 사용 -> 중복 방지)
        turn = st.session_state.turn
        if turn <= 3: stage = "초기"
        elif turn <= 7: stage = "중기"
        else: stage = "말기"
        
        # 덱에 카드가 남아있으면 뽑고, 만약 다 떨어졌으면(그럴 리 없지만) 랜덤 선택
        if st.session_state.decks[stage]:
            st.session_state.current_crisis = st.session_state.decks[stage].pop()
        else:
            st.session_state.current_crisis = random.choice(CRISES_POOL[stage])

# =============================================================================
# [2] 스타일(CSS) 설정 (가독성 수정판)
# =============================================================================

st.markdown("""
    <style>
        /* 버튼 스타일 */
        .stButton>button {
            width: 100%; height: auto; min-height: 50px; 
            font-size: 18px; font-weight: bold;
            border-radius: 12px; border: 1px solid #c0c0c0;
            background-color: white; color: #000000 !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.2s;
        }
        .stButton>button:hover {
            border-color: #007bff; color: #007bff !important; background-color: #eef6ff;
            transform: translateY(-2px);
        }
        
        /* [수정] 속보 박스 (신문지 회색 + 진한 테두리) */
        .question-text {
            font-size: 22px; font-weight: bold; text-align: center;
            margin: 20px 0; line-height: 1.6; word-break: keep-all;
            
            color: #000000 !important; /* 글자색: 검정 */
            background-color: #eeeeee !important; /* ★배경색: 신문지 회색 */
            border: 2px solid #555555; /* ★테두리: 진한 회색 */
            
            padding: 20px; border-radius: 5px; /* 모서리 각지게 */
            box-shadow: 4px 4px 0px rgba(0,0,0,0.1); /* 투박한 그림자 */
        }
        
        /* 상세 설명 박스 */
        .detail-box {
            margin-top: -10px; margin-bottom: 20px;
            background-color: #f8f9fa; 
            padding: 15px;
            border-radius: 0 0 10px 10px;
            font-size: 15px; color: #333333;
            border: 1px solid #e9ecef; border-top: none;
            line-height: 1.6;
        }
        
        /* 결과 카드 */
        .result-card {
            background-color: white; padding: 30px; border-radius: 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1); text-align: center; margin-bottom: 20px;
            color: black;
        }
        
        /* 명패 스타일 */
        .nameplate {
            display: block !important;
            background-color: #003478;
            border: 3px solid #c2a042;
            padding: 20px; border-radius: 15px;
            text-align: center; margin-bottom: 30px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }
    </style>
""", unsafe_allow_html=True)

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

# 진행바 (초기/중기/말기 표시)
if not st.session_state.game_over:
    turn = st.session_state.turn
    if turn <= 3: stage_name = "초기"
    elif turn <= 7: stage_name = "중기"
    else: stage_name = "말기"
    
    st.write(f"### 🗓️ 임기 {stage_name} ({turn}/10)")
    st.progress(min(1.0, (st.session_state.turn - 1) / 10))

# =============================================================================
# [6] 게임 플레이 / 엔딩 화면 (들여쓰기 수정 + 모든 기능 포함)
# =============================================================================

if st.session_state.game_over:
    # -------------------------------------------------------------------------
    # 0. 점수 및 칭호 계산 (여기가 들여쓰기 오류 났던 곳 - 수정됨)
    # -------------------------------------------------------------------------
    avg = sum(st.session_state.stats.values()) / 4
    budget = st.session_state.budget
    total_score = int(avg * 2 + budget)
    
    # 칭호 결정 (사용자 원본 기준 복구: 180/160/140)
    if "성공" in st.session_state.fail_msg or "만료" in st.session_state.fail_msg:
        if total_score >= 180: final_title = "전설의 성군"
        elif total_score >= 170: rank_title = "대통령의 대통령"
        elif total_score >= 160: final_title = "성공한 지도자"
        elif total_score >= 140: final_title = "노련한 정치가"
        elif total_score >= 120: final_title = "무난한 대통령"
        else: final_title = "아쉬운 대통령"
    else:
        final_title = "불명예 퇴진"
        total_score = int(total_score / 2) # 실패 시 점수 패널티

    # -------------------------------------------------------------------------
    # 1. 뉴스 헤드라인 (사라졌던 뉴스 복구)
    # -------------------------------------------------------------------------
    if "성공" in st.session_state.fail_msg or "만료" in st.session_state.fail_msg:
        st.balloons()
        st.subheader("📰 [호외] 임기 종료 특별 보도")
        
        if avg >= 70 and budget >= 60:
            st.success(f"### 🌟 역사상 가장 위대한 지도자, {st.session_state.player_name} 대통령 퇴임\n\n지지율과 경제 두 마리 토끼를 모두 잡은 '{final_title}'으로 기록될 것")
        elif avg >= 51 and budget >= 40:
            st.success(f"### ✅ 성공적인 국정 운영, 박수칠 때 떠나는 {st.session_state.player_name} 대통령\n\n숱한 위기 속에서도 대한민국을 안정적으로 이끌었다는 평가")
        elif budget < 20:
            st.warning(f"### 💸 '인기는 얻었으나 곳간은 비었다'... 포퓰리즘 논란 속 퇴임\n\n차기 정부에 막대한 재정 부담을 넘기게 되어... 국가 신용등급 우려")
        elif avg < 25:
            st.error(f"### 💀 역대 최저 지지율... {st.session_state.player_name} 대통령의 쓸쓸한 뒷모습\n\n국론 분열과 정책 실패로 얼룩진 5년... '식물 정부' 오명 남겨")
        else:
            st.info(f"### ⚖️ '공과 과' 뚜렷... {st.session_state.player_name} 정부 5년의 막을 내리다\n\n위기 관리 능력은 돋보였으나, 계층 간 갈등 해소는 과제로 남아")

    else:
        st.error(f"💀 GAME OVER: {st.session_state.fail_msg}")
        # 상세 실패 사유
        reason = ""
        if "부도" in st.session_state.fail_msg: reason = "국가 재정이 바닥나 IMF 구제금융을 신청했습니다."
        elif "자본" in st.session_state.fail_msg: reason = "국내 자본과 기업이 해외로 떠나고 주식 시장이 붕괴되었습니다."
        elif "중산층" in st.session_state.fail_msg: reason = "조세 저항과 탄핵 시위가 격화되었습니다."
        elif "노동자" in st.session_state.fail_msg: reason = "총파업으로 국가 기능이 마비되었습니다."
        elif "빈곤층" in st.session_state.fail_msg: reason = "생존권 투쟁이 폭동으로 번졌습니다."
        st.markdown(f"**📉 원인: {reason}**")

    # -------------------------------------------------------------------------
    # 2. 지지층/비토층 & 칭호 분석 (복구됨)
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.write("### 📊 국정 운영 성적표")
    
    sorted_stats = sorted(st.session_state.stats.items(), key=lambda x: x[1])
    best = sorted_stats[-1]
    worst = sorted_stats[0]
    
    col_a, col_b, col_c = st.columns(3)
    col_c.metric("🏆 최종 칭호", f"{final_title}")
    col_a.metric("❤️ 핵심 지지층", f"{best[0]} ({best[1]}%)")
    col_b.metric("💔 최대 비토층", f"{worst[0]} ({worst[1]}%)")
    
    st.caption(f"종합 점수: {total_score}점 (지지율 {avg:.1f} + 국고 {budget})")

    # -------------------------------------------------------------------------
    # 3. MBTI 카드 (이어서 계속 나오는 부분)
    # -------------------------------------------------------------------------
    my_type = get_politician_type(st.session_state.stats)
    style = RULING_STYLES[my_type]
    
    st.markdown("---")
    st.subheader("📸 나의 통치 스타일 (공유용)")
    
    st.markdown(f"""
    <div style="background-color: white; border: 2px solid {style['color']}; border-radius: 20px; padding: 30px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin-bottom: 20px;">
        <div style="font-size: 80px; margin-bottom: 10px;">{style['emoji']}</div>
        <h2 style="color: {style['color']}; margin: 0; font-size: 28px; font-weight: 900;">{style['title']}</h2>
        <p style="font-size: 18px; font-weight: bold; color: #333; margin-top: 10px;">{style['keywords'][0]} {style['keywords'][1]} {style['keywords'][2]}</p>
        <hr style="border: 0; border-top: 1px dashed #ddd; margin: 20px 0;">
        <p style="font-size: 15px; line-height: 1.6; color: #555; word-break: keep-all;">{style['desc']}</p>
        <div style="background-color: #f8f9fa; border-radius: 10px; padding: 15px; margin-top: 20px;">
            <p style="font-size: 14px; color: #777; margin: 0;">🗳️ 한 줄 어록</p>
            <p style="font-size: 18px; font-weight: bold; color: {style['color']}; margin: 5px 0 0 0;">"{style['quote']}"</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("👥 당신과 닮은 현실 정치인")
    pc1, pc2 = st.columns(2)
    with pc1:
        m1 = style['models'][0]
        img1 = get_model_image(m1['id'], m1['img'])
        st.image(img1, caption=m1['name'], use_container_width=True)
    with pc2:
        m2 = style['models'][1]
        img2 = get_model_image(m2['id'], m2['img'])
        st.image(img2, caption=m2['name'], use_container_width=True)

    # -------------------------------------------------------------------------
    # 4. 명예의 전당 (항상 펼침 상태)
    # -------------------------------------------------------------------------
    # 랭킹 저장
    if "score_saved" not in st.session_state:
        if "save_ranking" in globals():
            save_ranking(st.session_state.player_name if st.session_state.player_name else "익명", total_score, final_title)
        st.session_state.score_saved = True

    # 랭킹 표시 (조건 없이 바로 보여줌)
    if "load_ranking" in globals() and os.path.exists(FILE_RANKING):
        st.markdown("---")
        st.subheader("🏆 명예의 전당 (Top 10)")
        df_rank = load_ranking()
        if not df_rank.empty:
            st.dataframe(df_rank.head(10), hide_index=True)
        else:
            st.info("아직 랭킹이 없습니다.")

 # [풍자 후원] 특수활동비(비자금) 컨셉
    st.markdown("---")
    with st.expander("🙏대통령님, 특수활동비가 필요합니다🙏"):
        st.warning("""
        **"이 돈은 내역이 공개되지 않으며, 전액 개발자의 커피값(?)으로 횡령됩니다."**
        \n(※ 농협 3521436281053 정호원)
        """)

# -------------------------------------------------------------------------
    # [재시작 및 후원] (들여쓰기 수정됨)
    # -------------------------------------------------------------------------
    st.markdown("---")
    if st.button("🔄 새로운 대한민국 만들기", type="primary"):
        restart()

else:
    # =========================================================================
    # 게임 진행 화면 (설명 텍스트 복구)
    # =========================================================================
    c = st.session_state.current_crisis
    
    # 1. 이미지
    img_url = get_crisis_image(c.get('id', 99), c.get('img'))
    if img_url:
        st.image(img_url, use_container_width=True)
    
    # 2. 질문 (상황 설명)
    st.markdown(f"""
        <div class='question-text'>
            {c['desc']}
        </div>
    """, unsafe_allow_html=True)
    
    st.write("### 🫡 대통령님, 결단을 내려 주십시오")

    # 3. 선택지 버튼
    for i, opt in enumerate(c['options']):
        cost_txt = f"{'+' if opt['cost'] > 0 else ''}{opt['cost']}조"
        cost_color = "#d9534f" if opt['cost'] < 0 else "#0275d8"
        
        # 버튼 (제목만)
        if st.button(f"{i+1}. {opt['name']}", key=f"btn_{st.session_state.turn}_{i}", use_container_width=True):
            next_turn(i)
            st.rerun()
            
        # 설명 (아래 박스)
        st.markdown(f"""
        <div class="detail-box">
            <div style="display:flex; justify-content:space-between; font-weight:bold; margin-bottom:8px; border-bottom:1px solid #ddd; padding-bottom:5px;">
                <span>💰 예산: <span style="color:{cost_color}">{cost_txt}</span></span>
            </div>
            <div style="color: #333333;">
                {opt['detail']}
            </div>
        </div>
        """, unsafe_allow_html=True)
