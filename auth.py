import os
from jose import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

SUPABASE_JWT_SECRET = os.environ["SUPABASE_JWT_SECRET"]
SUPABASE_ISSUER = "https://oemlaccyxsxmhawgvzfg.supabase.co/auth/v1"


def get_user_id(
    creds: HTTPAuthorizationCredentials = Depends(security)
):
    try:
        token = creds.credentials

        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            issuer=SUPABASE_ISSUER,
        )

        return payload["sub"]

    except Exception as e:
        print("JWT ERROR:", repr(e))
        raise HTTPException(status_code=401, detail="Invalid token")
