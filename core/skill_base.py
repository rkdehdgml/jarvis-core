from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SkillResult:
    """스킬 실행 결과.

    Attributes:
        speech: TTS로 읽어줄 텍스트.
        data: 스킬이 반환하는 부가 데이터 (UI 표시, 후속 처리 등에 활용).
        success: 작업 성공 여부.
        follow_up: True이면 웨이크워드 없이 이어서 입력 대기.
    """
    speech: str
    success: bool
    data: dict = field(default_factory=dict)
    follow_up: bool = False


class Skill(ABC):
    """모든 스킬이 상속해야 하는 추상 기반 클래스.

    새 스킬 작성 방법:
        1. 이 클래스를 상속한 클래스를 skills/skill_<이름>.py 에 작성한다.
        2. 클래스 속성(name, description, triggers, examples)을 채운다.
        3. can_handle()과 execute()를 구현한다.
        4. 파일을 skills/ 폴더에 저장하면 레지스트리가 자동으로 인식한다.
    """

    # --- 클래스 속성 (서브클래스에서 반드시 재정의) ---

    name: str = ""
    """스킬 고유 식별자. 영문 소문자+언더스코어."""

    description: str = ""
    """스킬이 하는 일을 한 줄로 설명. 라우터가 참고한다."""

    triggers: list[str] = []
    """이 스킬과 연관된 핵심 키워드 목록."""

    examples: list[str] = []
    """라우팅 학습에 사용하는 예시 문장 목록."""

    # --- 추상 메서드 (서브클래스에서 반드시 구현) ---

    @abstractmethod
    def can_handle(self, intent: str, text: str) -> float:
        """이 명령을 처리할 수 있는지 판단한다.

        Args:
            intent: 라우터가 분석한 의도 키워드 (빈 문자열일 수 있음).
            text: 사용자 원문 입력.

        Returns:
            0.0 ~ 1.0 사이의 신뢰도.
            높을수록 이 스킬이 처리에 적합함을 의미한다.
            Router의 임계값(기본 0.4) 미만이면 선택되지 않는다.
        """

    @abstractmethod
    def execute(self, text: str, context: dict) -> SkillResult:
        """실제 작업을 수행하고 결과를 반환한다.

        Args:
            text: 사용자 원문 입력.
            context: 대화 맥락 딕셔너리. 이전 대화 기록, 세션 상태 등을 포함.
                     읽기/쓰기 모두 가능하며 변경 사항은 다음 턴에 유지된다.

        Returns:
            SkillResult. speech 필드가 TTS로 출력된다.
        """
