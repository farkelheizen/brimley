from brimley import entity


@entity(name="User")
class User:
    id: int
    username: str
    email: str
