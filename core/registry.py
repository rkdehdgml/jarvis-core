import importlib.util
import inspect
import logging
from pathlib import Path

from core.skill_base import Skill

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent.parent / "skills"


class SkillRegistry:
    """skills/ 폴더를 자동 스캔해 스킬을 로딩·보관한다.

    파일을 추가하는 것만으로 기능이 등록되는 핵심 메커니즘.
    본체 코드 수정 없이 skill_*.py 파일 추가/삭제만으로 기능을 제어한다.
    """

    def __init__(self) -> None:
        self._skills: list[Skill] = []
        self.load()

    def load(self) -> None:
        """skills/ 폴더의 skill_*.py 를 전부 스캔해 스킬을 로딩한다."""
        self._skills = []
        skill_files = sorted(_SKILLS_DIR.glob("skill_*.py"))

        if not skill_files:
            logger.warning("skills/ 폴더에 스킬 파일이 없습니다.")

        for path in skill_files:
            self._load_file(path)

        logger.info(f"스킬 {len(self._skills)}개 로딩 완료: {[s.name for s in self._skills]}")

    def reload(self) -> None:
        """런타임 중 skills/ 폴더를 재스캔한다.

        새 스킬 파일을 추가한 뒤 재시작 없이 반영할 때 호출한다.
        """
        logger.info("스킬 레지스트리 재로딩...")
        self.load()

    def get_all_skills(self) -> list[Skill]:
        """등록된 모든 스킬 인스턴스를 반환한다."""
        return list(self._skills)

    def _load_file(self, path: Path) -> None:
        module_name = f"skills.{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, Skill)
                    and obj is not Skill
                    and not inspect.isabstract(obj)
                ):
                    instance = obj()
                    self._skills.append(instance)
                    logger.debug(f"스킬 등록: {obj.__name__} ({path.name})")

        except Exception as e:
            # 한 스킬 로딩 실패가 나머지 스킬에 영향을 주지 않도록 격리
            logger.error(f"스킬 로딩 실패 [{path.name}]: {e}")
