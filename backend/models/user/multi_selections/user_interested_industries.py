from .user_multi_select_base import UserMultiSelectBase
from ..user_schemas import Industry

class UserInterestedIndustries(UserMultiSelectBase, table=True):
    __tablename__ = "user_interested_industries"
    
    interested_industry: Industry
