"""처음 실행 도우미: 설치 → 키 확인 → API 확인 → 국회 데이터 수집 → 지표 → 대조표 → 화면 열기.

시작하기_윈도우.bat / 시작하기_맥.command 를 더블클릭하면 이 파일이 실행된다.
이미 끝난 단계는 다시 돌려도 안전하다(수집은 캐시를 쓰고 증분으로 진행).
"""
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def say(msg):
    print(f"\n=== {msg}", flush=True)


def run(args, stop_on_fail=True):
    r = subprocess.run([PY, *args], cwd=ROOT)
    if r.returncode != 0 and stop_on_fail:
        print("\n[중단] 위 오류 메시지를 복사해서 Claude에게 보내 주세요.")
        input("엔터를 누르면 닫힙니다...")
        sys.exit(1)
    return r.returncode == 0


def read_env() -> dict:
    p = ROOT / ".env"
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def open_file(p: Path):
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["notepad.exe", str(p)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-e", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except OSError:
        pass


def main():
    if sys.version_info < (3, 10):
        print(f"Python 3.10 이상이 필요합니다(지금 {sys.version.split()[0]}). docs/keys.md 0번을 보세요.")
        input("엔터를 누르면 닫힙니다...")
        return

    say("1/7 필요한 프로그램 설치")
    run(["-m", "pip", "install", "-q", "-r", "requirements.txt"])

    say("2/7 키 파일(.env) 확인")
    env = ROOT / ".env"
    if not env.exists():
        shutil.copy(ROOT / ".env.example", env)
    keys = read_env()
    if not keys.get("ASSEMBLY_API_KEY"):
        print("열린국회정보 키가 아직 없습니다. 메모장이 열리면 ASSEMBLY_API_KEY= 뒤에 키를 붙여넣고 저장한 뒤,")
        print("이 창을 닫고 시작하기 파일을 다시 더블클릭하세요. (키 받는 법: docs/keys.md)")
        open_file(env)
        input("엔터를 누르면 닫힙니다...")
        return
    for k, label in [("NAVER_CLIENT_ID", "네이버 뉴스"), ("ANTHROPIC_API_KEY", "AI 판단")]:
        if not keys.get(k):
            print(f"- {label} 키 없음: 그 기능만 빼고 진행합니다.")

    say("3/7 국회 API 실제 호출 확인 → docs/api_check.md")
    run(["src/check_apis.py"])
    report = (ROOT / "docs" / "api_check.md").read_text(encoding="utf-8")
    if "실패" in report or "필드 불일치" in report:
        print("\n[확인 필요] 일부 API가 실패했거나 필드 이름이 다릅니다.")
        print("docs/api_check.md 파일 내용을 Claude에게 보내 주세요. 맞춘 뒤 다시 실행하면 됩니다.")
        open_file(ROOT / "docs" / "api_check.md")
        input("엔터를 누르면 닫힙니다...")
        return

    say("4/7 22대 국회 데이터 수집 (처음에는 오래 걸립니다. 중간에 꺼져도 다시 실행하면 이어서 합니다)")
    run(["src/update_assembly.py"])

    say("5/7 분석 지표 계산")
    run(["src/metrics.py"])
    run(["src/heuristics.py"], stop_on_fail=False)

    say("6/7 대조 검증표 → docs/verification.md")
    run(["src/verify_data.py"])
    if keys.get("NAVER_CLIENT_ID"):
        run(["src/news.py", "collect"], stop_on_fail=False)

    say("7/7 화면 열기: http://127.0.0.1:8000  (끄려면 이 창에서 Ctrl+C)")
    print("docs/api_check.md 와 docs/verification.md 내용을 Claude에게 보내 주시면 다음 단계로 넘어갑니다.")
    webbrowser.open("http://127.0.0.1:8000")
    subprocess.run([PY, "run.py"], cwd=ROOT)


if __name__ == "__main__":
    main()
