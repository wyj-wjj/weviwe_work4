from sqlalchemy import and_, or_, true

from app.domain.enums import AccountType, ContentLevel, ContentScope
from app.models.user import User


def visible_levels_for(user: User) -> set[str]:
    if user.account_type in {AccountType.ADMIN.value, AccountType.FULL_USER.value}:
        return {ContentLevel.GENERAL.value, ContentLevel.FULL.value}
    return {ContentLevel.GENERAL.value}


def can_view_all_department_scopes(user: User) -> bool:
    return user.account_type == AccountType.ADMIN.value


def scope_is_visible(user: User, scope_type: str, department_id: int | None) -> bool:
    if can_view_all_department_scopes(user):
        return True
    if scope_type == ContentScope.GLOBAL.value:
        return True
    return (
        scope_type == ContentScope.DEPARTMENT.value
        and user.department_id is not None
        and department_id == user.department_id
    )


def scope_filter(user: User, model):
    if can_view_all_department_scopes(user):
        return true()
    global_clause = model.scope_type == ContentScope.GLOBAL.value
    if user.department_id is None:
        return global_clause
    return or_(
        global_clause,
        and_(
            model.scope_type == ContentScope.DEPARTMENT.value,
            model.department_id == user.department_id,
        ),
    )
