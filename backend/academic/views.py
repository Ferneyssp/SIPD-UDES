from rest_framework import viewsets

from users.permissions import IsAdminOrReadOnly

from .models import AcademicPeriod, Program
from .serializers import AcademicPeriodSerializer, ProgramSerializer


class ProgramViewSet(viewsets.ModelViewSet):
    serializer_class = ProgramSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None
    http_method_names = ["get", "post", "put", "patch"]

    def get_queryset(self):
        from students.scoping import allowed_program_ids

        queryset = Program.objects.all()
        program_ids = allowed_program_ids(self.request.user)
        return queryset if program_ids is None else queryset.filter(id__in=program_ids)


class AcademicPeriodViewSet(viewsets.ModelViewSet):
    queryset = AcademicPeriod.objects.all()
    serializer_class = AcademicPeriodSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None
    http_method_names = ["get", "post", "put", "patch"]
