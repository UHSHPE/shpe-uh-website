from .user_multi_select_base import UserMultiSelectBase

class UserCountryOrigin(UserMultiSelectBase, table=True):
    __tablename__ = "user_country_origin"
    
    country_origin: str
