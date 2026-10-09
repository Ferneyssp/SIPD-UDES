"""
Ámbito de acceso a estudiantes según el rol.

- Administrador: todos los estudiantes.
- Coordinador: programas asignados; si no tiene programas asignados, todos.
- Profesor: sólo estudiantes de sus programas asignados.
"""
from users.models import Role


def allowed_program_ids(user):
    """None = sin restricción; lista (posiblemente vacía) = programas permitidos."""
    if user.role == Role.ADMIN:
        return None
    program_ids = list(user.programs.values_list("id", flat=True))
    if user.role == Role.COORDINATOR and not program_ids:
        return None
    return program_ids


def scope_queryset(queryset, user, program_field: str = "program_id"):
    program_ids = allowed_program_ids(user)
    if program_ids is None:
        return queryset
    return queryset.filter(**{f"{program_field}__in": program_ids})


def user_can_access_student(user, student) -> bool:
    program_ids = allowed_program_ids(user)
    return program_ids is None or student.program_id in program_ids
