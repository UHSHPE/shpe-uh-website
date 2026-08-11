from sqlmodel import SQLModel, Field

class UserMultiSelectBase(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
