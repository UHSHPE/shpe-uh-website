from models.event import Event

POINT_VALUES: dict[str, int] = {}


def event_point_type(event: Event) -> str:
    raise NotImplementedError


def sign_in_points(event: Event, *, brought_new_member: bool = False, wore_shirt: bool = False) -> int:
    raise NotImplementedError
