import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from news import clean, match_member, region_words

M = {"name": "가나다", "party": "갑을당", "district": "서울 종로구"}


def test_clean():
    assert clean("<b>가나다</b> &quot;의원&quot;") == '가나다 "의원"'


def test_region_words():
    assert region_words("서울 종로구") == ["서울", "종로"]
    assert region_words("비례대표") == []


def test_match_rules():
    assert match_member("가나다 의원, 갑을당 원내대변인", M)[0]
    assert match_member("종로 지역 현안에 갑을당 가나다", M)[0]          # 정당+지역구
    assert not match_member("배우 가나다, 새 영화 개봉", M)[0]           # 동명이인
    assert not match_member("가나다 의원이 말했다", M)[0]               # 이름+의원만으로는 부족
    assert not match_member("다른 사람 의원", M)[0]
