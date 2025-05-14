from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from .models import User, Course, Lesson, Attendance, Grade, Group
from .serializers import UserSerializer, CourseSerializer, LessonSerializer, AttendanceSerializer, GradeSerializer, GroupSerializer
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from .permissions import IsTeacher, IsStudent, IsAdminOrOwner
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError, ObjectDoesNotExist, PermissionDenied
from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError as DRFValidationError

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        elif self.action == 'destroy':
            return [permissions.IsAuthenticated(), IsTeacher()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if self.request.user.is_staff or self.request.user.is_teacher():
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)

    def create(self, request, *args, **kwargs):
        try:
            role = request.data.get('role', 'student')
            
            # Если пользователь пытается создать учителя
            if role == 'teacher':
                # Проверяем, что запрос от аутентифицированного пользователя-учителя
                if not request.user.is_authenticated or not request.user.is_teacher():
                    raise ValidationError("Только учителя могут создавать других учителей")
            elif role != 'student':
                raise ValidationError("Недопустимая роль. Допустимые значения: 'student', 'teacher'")
            
            email = request.data.get('email')
            if User.objects.filter(email=email).exists():
                raise ValidationError("Пользователь с таким email уже существует")
            
            return super().create(request, *args, **kwargs)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # Проверяем, что пользователь обновляет свой профиль или является учителем
        if instance.id != request.user.id and not request.user.is_teacher():
            return Response(
                {'error': 'Вы можете обновлять только свой профиль'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.prefetch_related('students')
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff or self.request.user.is_teacher():
            return self.queryset
        return self.queryset.filter(students=self.request.user)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'add_student', 'remove_student']:
            return [IsAuthenticated(), IsTeacher()]
        return [IsAuthenticated()]

    def check_teacher_permission(self):
        if not self.request.user.is_teacher():
            raise PermissionDenied("Только преподаватели могут управлять группами")

    def validate_students(self, students, current_group=None):
        """Проверяет, что студенты не состоят в других группах"""
        for student_id in students:
            try:
                student = User.objects.get(id=student_id, role='student')
                # Проверяем, не состоит ли студент в другой группе
                other_groups = Group.objects.filter(students=student)
                if current_group:
                    other_groups = other_groups.exclude(pk=current_group.pk)
                
                if other_groups.exists():
                    raise DjangoValidationError(
                        f"Студент {student.get_full_name()} уже состоит в группе {other_groups.first().name}"
                    )
            except User.DoesNotExist:
                raise DjangoValidationError(f"Студент с ID {student_id} не найден")

    def perform_create(self, serializer):
        try:
            serializer.save()
        except (DjangoValidationError, DRFValidationError) as e:
            raise DRFValidationError(detail=str(e))

    def perform_update(self, serializer):
        try:
            serializer.save()
        except (DjangoValidationError, DRFValidationError) as e:
            raise DRFValidationError(detail=str(e))

    def create(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()
            
            # Проверка наличия обязательных полей
            if 'name' not in request.data:
                raise DjangoValidationError("Поле 'name' обязательно")
            
            # Проверка уникальности имени группы
            name = request.data.get('name')
            if Group.objects.filter(name=name).exists():
                raise DjangoValidationError(f"Группа с именем '{name}' уже существует")
            
            # Проверка списка студентов
            students = request.data.get('student_ids', [])
            if not isinstance(students, list):
                raise DjangoValidationError("Поле 'student_ids' должно быть списком")
            
            # Проверяем, что студенты не состоят в других группах
            self.validate_students(students)
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
            
        except DjangoValidationError as e:
            return Response({'error': e.messages[0] if e.messages else str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

    def update(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()
            instance = self.get_object()
            
            # Проверка списка студентов только если он указан в запросе
            if 'student_ids' in request.data:
                students = request.data.get('student_ids', [])
                if not isinstance(students, list):
                    raise DjangoValidationError("Поле 'student_ids' должно быть списком")
                
                # Проверяем, что студенты не состоят в других группах
                self.validate_students(students, instance)
            
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            
            return Response(serializer.data)
            
        except DjangoValidationError as e:
            return Response({'error': e.messages[0] if e.messages else str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Группа не найдена'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    def destroy(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Группа не найдена'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def add_student(self, request, pk=None):
        """Добавить студента в группу"""
        try:
            group = self.get_object()
            student_id = request.data.get('student_id')
            if not student_id:
                raise DjangoValidationError("student_id обязателен")

            try:
                student = User.objects.get(id=student_id, role='student')
            except User.DoesNotExist:
                raise DjangoValidationError(f"Студент с ID {student_id} не найден")

            # Проверяем, не состоит ли студент в другой группе
            self.validate_students([student_id], group)

            group.students.add(student)
            serializer = self.get_serializer(group)
            return Response(serializer.data)

        except DjangoValidationError as e:
            return Response({'error': e.messages[0] if e.messages else str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['post'])
    def remove_student(self, request, pk=None):
        """Удалить студента из группы"""
        try:
            group = self.get_object()
            student_id = request.data.get('student_id')
            if not student_id:
                raise DjangoValidationError("student_id обязателен")

            try:
                student = User.objects.get(id=student_id, role='student')
            except User.DoesNotExist:
                raise DjangoValidationError(f"Студент с ID {student_id} не найден")

            if student not in group.students.all():
                raise DjangoValidationError(f"Студент не состоит в этой группе")

            group.students.remove(student)
            serializer = self.get_serializer(group)
            return Response(serializer.data)

        except DjangoValidationError as e:
            return Response({'error': e.messages[0] if e.messages else str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Course.objects.none()

        user = self.request.user
        if user.is_teacher():
            return Course.objects.filter(teacher=user)
        # Получаем курсы через группы студента
        return Course.objects.filter(groups__in=user.student_groups.all()).distinct()

    def check_teacher_permission(self):
        if not self.request.user.is_teacher():
            raise PermissionDenied("Только преподаватели могут управлять курсами")

    def perform_create(self, serializer):
        self.check_teacher_permission()
        serializer.save(teacher=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()
            
            # Проверка обязательных полей
            required_fields = ['title', 'semester', 'year']
            for field in required_fields:
                if field not in request.data:
                    raise ValidationError(f"Поле '{field}' обязательно")
            
            # Проверка года
            year = request.data.get('year')
            if not isinstance(year, int) or year < 2000 or year > 2100:
                raise ValidationError("Год должен быть числом между 2000 и 2100")
            
            # Проверка семестра
            semester = request.data.get('semester')
            if semester not in ['fall', 'spring']:
                raise ValidationError("Семестр должен быть 'fall' или 'spring'")
            
            return super().create(request, *args, **kwargs)
        except (ValidationError, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()
            instance = self.get_object()
            
            if instance.teacher != self.request.user:
                raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            
            # Проверка года если он указан
            year = request.data.get('year')
            if year is not None:
                if not isinstance(year, int) or year < 2000 or year > 2100:
                    raise ValidationError("Год должен быть числом между 2000 и 2100")
            
            # Проверка семестра если он указан
            semester = request.data.get('semester')
            if semester is not None and semester not in ['fall', 'spring']:
                raise ValidationError("Семестр должен быть 'fall' или 'spring'")
            
            return super().update(request, *args, **kwargs)
        except (ValidationError, PermissionDenied, ObjectDoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.teacher != self.request.user:
                raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            return super().destroy(request, *args, **kwargs)
        except (PermissionDenied, ObjectDoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='add-group')
    def add_group(self, request, pk=None):
        try:
            course = self.get_object()
            
            # Проверяем, что текущий пользователь - учитель этого курса
            if course.teacher != self.request.user:
                raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            
            # Получаем ID группы из запроса
            group_id = request.data.get('group_id')
            if not group_id:
                raise ValidationError("group_id обязателен")
            
            try:
                group = Group.objects.get(id=group_id)
            except Group.DoesNotExist:
                raise ValidationError(f"Группа с ID {group_id} не найдена")
            
            # Проверяем, не добавлена ли уже эта группа на курс
            if course.groups.filter(id=group_id).exists():
                raise ValidationError("Эта группа уже добавлена на курс")
            
            # Добавляем группу на курс
            course.groups.add(group)
            
            # Возвращаем обновленные данные курса
            serializer = self.get_serializer(course)
            return Response(serializer.data)
            
        except (ValidationError, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Lesson.objects.none()

        user = self.request.user
        if user.is_teacher():
            return Lesson.objects.filter(course__teacher=user).select_related('course')
        return Lesson.objects.filter(course__groups__students=user).select_related('course').distinct()

    def check_teacher_permission(self):
        if not self.request.user.is_teacher():
            raise PermissionDenied("Только преподаватели могут управлять уроками")

    def create(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()
            
            # Проверка обязательных полей
            required_fields = ['course_id', 'date', 'topic']
            for field in required_fields:
                if field not in request.data:
                    raise DjangoValidationError(f"Поле '{field}' обязательно")
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
            
        except (DjangoValidationError, DRFValidationError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

    def update(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()
            instance = self.get_object()
            
            # Проверяем, является ли пользователь преподавателем этого курса
            if instance.course.teacher != request.user:
                raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            
            return Response(serializer.data)
            
        except (DjangoValidationError, DRFValidationError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Урок не найден'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.course.teacher != request.user:
                raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            return super().destroy(request, *args, **kwargs)
        except (PermissionDenied, ObjectDoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Attendance.objects.none()

        user = self.request.user
        if user.is_teacher():
            return Attendance.objects.filter(
                lesson__course__teacher=user
            ).select_related('student', 'lesson')
        return Attendance.objects.filter(student=user)

    def check_teacher_permission(self):
        if not self.request.user.is_teacher():
            raise PermissionDenied("Только преподаватели могут управлять посещаемостью")

    def create(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()
            
            # Проверка обязательных полей
            required_fields = ['lesson_id', 'student_id', 'is_present']
            for field in required_fields:
                if field not in request.data:
                    raise DjangoValidationError(f"Поле '{field}' обязательно")
            
            # Проверяем права на урок
            lesson_id = request.data.get('lesson_id')
            try:
                lesson = Lesson.objects.get(id=lesson_id)
                if lesson.course.teacher != request.user:
                    raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            except Lesson.DoesNotExist:
                raise DjangoValidationError(f"Урок с ID {lesson_id} не найден")
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
            
        except (DjangoValidationError, DRFValidationError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

    def update(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()
            instance = self.get_object()
            
            if instance.lesson.course.teacher != request.user:
                raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            
            return Response(serializer.data)
            
        except (DjangoValidationError, DRFValidationError) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Отметка посещаемости не найдена'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.lesson.course.teacher != request.user:
                raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            return super().destroy(request, *args, **kwargs)
        except (PermissionDenied, ObjectDoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GradeViewSet(viewsets.ModelViewSet):
    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Grade.objects.none()

        user = self.request.user
        if user.is_teacher():
            return Grade.objects.filter(
                lesson__course__teacher=user
            ).select_related('student', 'lesson')
        return Grade.objects.filter(student=user)

    def check_teacher_permission(self):
        if not self.request.user.is_teacher():
            raise PermissionDenied("Только преподаватели могут управлять оценками")
        
    def create(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()
            
            # Проверка обязательных полей
            required_fields = ['lesson', 'student', 'value']
            for field in required_fields:
                if field not in request.data:
                    raise ValidationError(f"Поле '{field}' обязательно")
            
            # Проверка существования урока
            lesson_id = request.data.get('lesson')
            try:
                lesson = Lesson.objects.get(id=lesson_id)
                if lesson.course.teacher != self.request.user:
                    raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            except Lesson.DoesNotExist:
                raise ValidationError(f"Урок с ID {lesson_id} не найден")
            
            # Проверка существования студента
            student_id = request.data.get('student')
            try:
                student = User.objects.get(id=student_id, role='student')
                # Проверка, что студент записан на курс
                if not student.course_set.filter(id=lesson.course.id).exists():
                    raise ValidationError(f"Студент не записан на этот курс")
            except User.DoesNotExist:
                raise ValidationError(f"Студент с ID {student_id} не найден")
            
            # Проверка значения оценки
            value = request.data.get('value')
            if not isinstance(value, (int, float)) or value < 0 or value > 100:
                raise ValidationError("Оценка должна быть числом от 0 до 100")
            
            # Проверка, что оценка еще не выставлена
            if Grade.objects.filter(lesson=lesson, student=student).exists():
                raise ValidationError("Оценка для этого студента уже выставлена")
            
            return super().create(request, *args, **kwargs)
        except (ValidationError, PermissionDenied) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()
            instance = self.get_object()
            
            if instance.lesson.course.teacher != self.request.user:
                raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            
            # Проверка значения оценки если указано
            value = request.data.get('value')
            if value is not None:
                if not isinstance(value, (int, float)) or value < 0 or value > 100:
                    raise ValidationError("Оценка должна быть числом от 0 до 100")
            
            return super().update(request, *args, **kwargs)
        except (ValidationError, PermissionDenied, ObjectDoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if instance.lesson.course.teacher != self.request.user:
                raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            return super().destroy(request, *args, **kwargs)
        except (PermissionDenied, ObjectDoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def my_grades(self, request):
        if not request.user.is_student():
            raise PermissionDenied("Только студенты могут просматривать свои оценки")
        grades = self.get_queryset().filter(student=request.user)
        serializer = self.get_serializer(grades, many=True)
        return Response(serializer.data)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer