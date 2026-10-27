# 케이스 도서관 시제품 (윤석열 정부, 한국갤럽 데일리 오피니언)

> **데이터 이용 조건 주의**: 이 시제품은 비영리 연구용이다. 원자료 저작권은 한국갤럽에 있으며,
> 상업적으로 이용하기 전에는 반드시 한국갤럽과 이용 조건을 협의해야 한다.
> 원본 PDF는 `data/raw/`에만 두고 git에 올리지 않는다.

## 실행
```
pip install -r requirements.txt
python src/collect.py --limit 10   # 시험 수집
python src/collect.py              # 전체 수집
```

## 산출물
- `data/report_index.csv` : 갤럽 리포트 목록에서 얻은 데일리 오피니언 호수·주차·게시일 (2022~2025년)
- `data/manifest.csv` : 대상 기간 호수별 수집 상태 + 보고서가 없는 주 목록(`no_report_this_week`)
- `data/robots_check.txt` : robots.txt 확인 기록
