from .user_multi_select_base import UserMultiSelectBase
from ..user_enums import RaceEthnicity

class UserRaceEthnicity(UserMultiSelectBase, table=True):
    __tablename__ = "user_race_ethnicity"
    
    race_and_ethnicity: RaceEthnicity
    