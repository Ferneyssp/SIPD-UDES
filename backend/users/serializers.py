from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from academic.models import Program

from .models import Role, User


class ProgramMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ["id", "code", "name"]


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    programs = ProgramMiniSerializer(many=True, read_only=True)
    program_ids = serializers.PrimaryKeyRelatedField(
        source="programs", queryset=Program.objects.all(), many=True, write_only=True, required=False
    )
    password = serializers.CharField(write_only=True, required=False, min_length=8, style={"input_type": "password"})
    can_manage_users_effective = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name", "role", "role_display",
            "is_active", "programs", "program_ids", "can_manage_users", "can_manage_users_effective",
            "password", "created_at", "updated_at", "last_login",
        ]
        read_only_fields = ["created_at", "updated_at", "last_login"]

    def validate_email(self, value):
        value = value.strip().lower()
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un usuario con este correo.")
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "La contraseña es obligatoria al crear un usuario."})
        if attrs.get("password"):
            candidate = User(username=attrs.get("username", getattr(self.instance, "username", "")), email=attrs.get("email", ""))
            password_validation.validate_password(attrs["password"], candidate)
        role = attrs.get("role", getattr(self.instance, "role", None))
        if role != Role.COORDINATOR:
            attrs["can_manage_users"] = False
        return attrs

    def create(self, validated_data):
        programs = validated_data.pop("programs", [])
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        user.programs.set(programs)
        return user

    def update(self, instance, validated_data):
        programs = validated_data.pop("programs", None)
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        if programs is not None:
            instance.programs.set(programs)
        return instance


class ProfileSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    programs = ProgramMiniSerializer(many=True, read_only=True)
    can_manage_users_effective = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name", "role", "role_display", "is_active",
            "programs", "can_manage_users_effective", "created_at", "last_login",
        ]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    """Acepta nombre de usuario o correo electrónico."""

    username = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"})

    default_error = "Credenciales incorrectas."

    def validate(self, attrs):
        identifier = attrs["username"].strip()
        username = identifier
        if "@" in identifier:
            match = User.objects.filter(email__iexact=identifier).only("username").first()
            username = match.username if match else identifier
        user = authenticate(request=self.context.get("request"), username=username, password=attrs["password"])
        if user is None:
            inactive = User.objects.filter(username=username, is_active=False).first()
            if inactive and inactive.check_password(attrs["password"]):
                raise serializers.ValidationError({"detail": "El usuario se encuentra desactivado."})
            raise serializers.ValidationError({"detail": self.default_error})
        refresh = RefreshToken.for_user(user)
        refresh["role"] = user.role
        attrs["user"] = user
        attrs["tokens"] = {"access": str(refresh.access_token), "refresh": str(refresh)}
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField(min_length=8)
    confirm_password = serializers.CharField()

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "La contraseña actual no es correcta."})
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Las contraseñas no coinciden."})
        if attrs["new_password"] == attrs["current_password"]:
            raise serializers.ValidationError({"new_password": "La nueva contraseña debe ser diferente a la actual."})
        password_validation.validate_password(attrs["new_password"], user)
        return attrs
