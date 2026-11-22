from ..database import service_engine


def users_engine():
    return service_engine("users")
