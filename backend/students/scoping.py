"""
Ámbito de acceso a estudiantes según el rol.

- Administrador: todos los estudiantes.
- Coordinador: sólo los estudiantes de sus programas asignados. Sin programas asignados no
  ve ninguno: ante la duda, el acceso se deniega.
"""
from users.models import Role


def allowed_program_ids(user):
    """None = sin restricción; lista (posiblemente vacía) = programas permitidos."""
    if user.role == Role.ADMIN:
        return None
    if user.role != Role.COORDINATOR:
        return []
    return list(user.programs.values_list("id", flat=True))


def scope_queryset(queryset, user, program_field: str = "program_id"):
    program_ids = allowed_program_ids(user)
    if program_ids is None:
        return queryset
    return queryset.filter(**{f"{program_field}__in": program_ids})


def user_can_access_student(user, student) -> bool:
    program_ids = allowed_program_ids(user)
    return program_ids is None or student.program_id in program_ids


def eligible_responsibles(program_id, queryset=None):
    """Quienes pueden ser responsables de un seguimiento o una alerta: coordinadores activos asignados
    al programa del estudiante. El Administrador nunca es responsable."""
    from users.models import User

    queryset = queryset if queryset is not None else User.objects.filter(is_active=True)
    return queryset.filter(role=Role.COORDINATOR, programs__id=program_id).distinct()


def can_be_responsible(user, student) -> bool:
    return bool(user and user.is_active and user.role == Role.COORDINATOR and user_can_access_student(user, student))
