import os

import httpx
from fastapi import HTTPException, Request
from sqlalchemy.orm import sessionmaker

from ..database import service_engine


engine = service_engine("estimate")
Sessions = sessionmaker(engine)


async def users_get(request, path):
    endpoint = os.getenv("USERS_URL", "http://127.0.0.1:8000")
    try:
        async with httpx.AsyncClient(base_url=endpoint, timeout=5, trust_env=False) as client:
            response = await client.get("/api/v1/" + path, cookies={"session": request.cookies.get("session", "")})
    except httpx.RequestError:
        raise HTTPException(503, "Сервис пользователей временно недоступен") from None
    if response.status_code == 401:
        raise HTTPException(401, "Войдите в аккаунт")
    if response.status_code == 404:
        raise HTTPException(404, "Автомобиль не найден")
    if response.status_code != 200:
        raise HTTPException(503, "Сервис пользователей временно недоступен")
    return response.json()


async def owner(request: Request):
    return (await users_get(request, "users/me"))["id"]



