from fastapi import Header, HTTPException, status

from blueframe.security.session_token import SessionTokenVerifier


def session_dependency(verifier: SessionTokenVerifier):
    def require_session(
        x_blueframe_session: str | None = Header(default=None),
    ) -> None:
        if not verifier.verify(x_blueframe_session):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "session_unauthorized", "message": "桌面会话无效"},
            )

    return require_session
