from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"
    COORDINATOR = "COORDINATOR", "Coordinador académico"
    PROFESSOR = "PROFESSOR", "Profesor"


class SipdUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """Usuario institucional. La contraseña se almacena con hash (PBKDF2 por defecto)."""

    email = models.EmailField("correo electrónico", unique=True)
    role = models.CharField("rol", max_length=20, choices=Role.choices, default=Role.PROFESSOR)
    programs = models.ManyToManyField(
        "academic.Program",
        blank=True,
        related_name="users",
        help_text="Programas a los que el usuario tiene acceso. Profesores: obligatorio. "
        "Coordinadores: si está vacío, acceden a todos los programas.",
    )
    can_manage_users = models.BooleanField(
        "puede administrar usuarios",
        default=False,
        help_text="Permiso explícito para que un coordinador gestione usuarios.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SipdUserManager()

    class Meta:
        ordering = ["username"]
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    @property
    def is_admin_role(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def can_manage_users_effective(self) -> bool:
        return self.is_admin_role or (self.role == Role.COORDINATOR and self.can_manage_users)

    @property
    def display_name(self) -> str:
        return self.get_full_name() or self.username

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"
