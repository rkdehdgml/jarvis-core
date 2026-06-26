"""browser_specs 검증: registry.py에 아직 등록 전이므로 로컬에서 직접 register.

실행: python -m tests.test_browser_specs
"""
from commands.registry import register, COMMAND_MAP
from commands.specs import browser_specs


def main() -> None:
    if "BROWSER_OPEN_URL" not in COMMAND_MAP:
        register(browser_specs.SPECS)

    spec = COMMAND_MAP["BROWSER_OPEN_URL"]
    # shell bridge: os.startfile() 사용 — explorer.exe exit code 1 오판 문제 해결
    assert spec.bridge == "shell", "bridge는 shell이어야 한다(os.startfile 직접 호출)"
    assert spec.binary is None, "shell bridge는 binary를 사용하지 않는다"
    assert spec.build_args({"url": "https://example.com"}) == ["https://example.com"]

    print("test_browser_specs 통과")


if __name__ == "__main__":
    main()
