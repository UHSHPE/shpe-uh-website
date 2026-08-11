from .user_multi_select_base import UserMultiSelectBase
from ..user_enums import ProfDev

class UserProfDev(UserMultiSelectBase, table=True):
    __tablename__ = "user_prof_dev"
    
    prof_dev: ProfDev
