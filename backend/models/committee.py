from sqlmodel import SQLModel, Field

from models.user.user_enums import Role

class ChairOut(SQLModel):
    first_name: str
    last_name: str
    personal_email: str

class MemberOut(SQLModel):
    id: int
    first_name: str
    last_name: str
    personal_email: str
    phone_num: str

class CommitteeOut(SQLModel):
    id: int
    name: str
    description: str
    is_member: bool
    is_chair: bool
    chairs: list[ChairOut] = []

class Committee(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    chair_role: Role | None = Field(default=None)
    # False for the E-Board "committees" seeded only so EventHost can point
    # at an officer position (or the generic bare "eboard" sheet value) --
    # they aren't real committees members can join. get_all_committees()
    # filters on this so /committees is unchanged for members.
    joinable: bool = Field(default=True)

class CommitteeMembership(SQLModel, table=True):
    user_id: int = Field(foreign_key="user.id", primary_key=True)
    committee_id: int = Field(foreign_key="committee.id", primary_key=True)
    status: bool = Field(default=True)
    is_chair: bool = Field(default=False)
    