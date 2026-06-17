def get_input(prompt: str = "you> ") -> str:
    """콘솔에서 사용자 텍스트를 입력받는다.

    개발/디버그용으로 시작했지만, STEP 14의 채팅 채널이 동일한
    인터페이스(텍스트를 받아 반환)를 따르므로 그대로 채팅 입력 경로의
    토대가 된다.
    """
    return input(prompt).strip()
