from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from .models import (
    User, Course, Lesson, Attendance, Grade, Group,
    SEMESTER_SPRING, SEMESTER_AUTUMN, VALID_SEMESTER_VALUES
)
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
from django.utils.dateparse import parse_datetime
from django.utils import timezone

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
        if getattr(self, 'swagger_fake_view', False):  # Проверка для swagger
            return User.objects.none()
            
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
        if getattr(self, 'swagger_fake_view', False):  # Проверка для swagger
            return Group.objects.none()
        
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
            
            # Проверка обязательных полей
            if 'name' not in request.data:
                raise ValidationError("Поле 'name' обязательно")
            
            # Проверка уникальности имени группы
            name = request.data.get('name')
            if Group.objects.filter(name=name).exists():
                raise ValidationError(f"Группа с именем '{name}' уже существует")
            
            # Создание группы
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
            
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

    @action(detail=True, methods=['post'], url_path='add-student')
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

    @action(detail=True, methods=['post'], url_path='remove-student')
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

    @action(detail=True, methods=['get'], url_path='list-students')
    def list_students(self, request, pk=None):
        """Получить список студентов группы"""
        try:
            group = self.get_object()
            students = group.students.all()
            serializer = UserSerializer(students, many=True)
            return Response(serializer.data)
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Группа не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'], url_path='bulk-add-students')
    def bulk_add_students(self, request, pk=None):
        """Массовое добавление студентов в группу"""
        try:
            self.check_teacher_permission()
            group = self.get_object()
            
            student_ids = request.data.get('student_ids', [])
            if not isinstance(student_ids, list):
                raise ValidationError("Поле 'student_ids' должно быть списком")
            
            # Проверяем, что студенты не состоят в других группах
            try:
                self.validate_students(student_ids, group)
            except DjangoValidationError as e:
                raise ValidationError(e.messages[0] if e.messages else str(e))
            
            # Добавляем студентов в группу
            students = User.objects.filter(id__in=student_ids, role='student')
            group.students.add(*students)
            
            serializer = self.get_serializer(group)
            return Response(serializer.data)
            
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Группа не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]

    def check_teacher_permission(self):
        if self.request.user.role != 'teacher':
            raise PermissionDenied("Только преподаватели могут управлять курсами")

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):  # Проверка для swagger
            return Course.objects.none()
            
        user = self.request.user
        if user.role == 'teacher':
            return Course.objects.filter(teacher=user)
        return Course.objects.filter(groups__students=user)

    def get_object(self):
        obj = super().get_object()
        if self.request.method not in ['GET', 'HEAD', 'OPTIONS']:
            if not self.request.user.is_teacher():
                raise PermissionDenied("Только преподаватели могут управлять курсами")
            if obj.teacher != self.request.user:
                raise PermissionDenied("Вы не являетесь преподавателем этого курса")
        return obj

    def perform_create(self, serializer):
        self.check_teacher_permission()
        serializer.save(teacher=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()
            
            # Проверка обязательных полей
            required_fields = ['name', 'semester', 'year']
            for field in required_fields:
                if field not in request.data:
                    raise ValidationError(f"Поле '{field}' обязательно")
            
            # Проверка семестра
            semester = request.data.get('semester')
            if semester not in VALID_SEMESTER_VALUES:
                raise ValidationError(f"Семестр должен быть '{SEMESTER_SPRING}' или '{SEMESTER_AUTUMN}'")
            
            # Проверка года
            year = request.data.get('year')
            if not isinstance(year, int) or year < 2024:
                raise ValidationError("Год должен быть целым числом не меньше 2024")
            
            # Создание курса
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
            
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            
            # Проверка семестра если он указан
            semester = request.data.get('semester')
            if semester is not None and semester not in VALID_SEMESTER_VALUES:
                raise ValidationError(f"Семестр должен быть '{SEMESTER_SPRING}' или '{SEMESTER_AUTUMN}'")
            
            # Проверка года если он указан
            year = request.data.get('year')
            if year is not None:
                try:
                    year = int(year)
                    if year < 2024:
                        raise ValidationError("Год должен быть числом не меньше 2024")
                except (TypeError, ValueError):
                    raise ValidationError("Год должен быть числом")
            
            serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['post'], url_path='add-group')
    def add_group(self, request, pk=None):
        try:
            course = self.get_object()
            group_id = request.data.get('group_id')
            if not group_id:
                raise ValidationError("Необходимо указать group_id")

            try:
                group = Group.objects.get(id=group_id)
            except Group.DoesNotExist:
                return Response(
                    {'error': f"Группа с ID {group_id} не найдена"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            course.groups.add(group)
            serializer = self.get_serializer(course)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='my-grades')
    def my_grades(self, request, pk=None):
        """Get all grades for a student in a course"""
        course = self.get_object()
        if request.user.role != 'student':
            raise PermissionDenied("Только студенты могут просматривать свои оценки")
        
        if not Group.objects.filter(students=request.user, courses=course).exists():
            raise ValidationError("Вы не записаны на этот курс")

        grades = Grade.objects.filter(
            lesson__course=course,
            student=request.user
        )
        serializer = GradeSerializer(grades, many=True)
        return Response(serializer.data)


class LessonViewSet(viewsets.ModelViewSet):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [IsAuthenticated]

    def check_teacher_permission(self):
        if self.request.user.role != 'teacher':
            raise PermissionDenied("Только преподаватели могут управлять уроками")

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):  # Проверка для swagger
            return Lesson.objects.none()
            
        user = self.request.user
        if user.role == 'teacher':
            return Lesson.objects.filter(course__teacher=user)
        return Lesson.objects.filter(course__groups__students=user)

    def create(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()

            # Проверка обязательных полей
            required_fields = ['course_id', 'date', 'topic']
            for field in required_fields:
                if field not in request.data:
                    raise ValidationError(f"Поле '{field}' обязательно")

            # Проверка существования курса
            course_id = request.data.get('course_id')
            try:
                course = Course.objects.get(id=course_id)
                if course.teacher != request.user:
                    raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            except Course.DoesNotExist:
                raise ValidationError(f"Курс с ID {course_id} не найден")

            # Проверка даты
            date = request.data.get('date')
            try:
                date = parse_datetime(date)
                if date < timezone.now():
                    raise ValidationError("Дата урока не может быть в прошлом")
            except (ValueError, TypeError):
                raise ValidationError("Неверный формат даты")

            # Создание урока
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

    @action(detail=True, methods=['post'], url_path='bulk-grades')
    def bulk_grades(self, request, pk=None):
        """Bulk assign grades for a lesson"""
        lesson = self.get_object()
        if request.user != lesson.course.teacher:
            raise PermissionDenied("Вы не являетесь преподавателем этого курса")

        grades = []
        for grade_data in request.data:
            student_id = grade_data.get('student_id')
            value = grade_data.get('value')
            
            try:
                student = User.objects.get(id=student_id, role='student')
                if not Group.objects.filter(students=student, courses=lesson.course).exists():
                    raise ValidationError(f"Студент с ID {student_id} не записан на этот курс")
                
                grade = Grade.objects.create(
                    lesson=lesson,
                    student=student,
                    value=value
                )
                grades.append(grade)
            except User.DoesNotExist:
                raise ValidationError(f"Студент с ID {student_id} не найден")

        serializer = GradeSerializer(grades, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AttendanceViewSet(viewsets.ModelViewSet):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]

    def check_teacher_permission(self):
        if self.request.user.role != 'teacher':
            raise PermissionDenied("Только преподаватели могут управлять посещаемостью")

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):  # Проверка для swagger
            return Attendance.objects.none()
            
        user = self.request.user
        if user.role == 'teacher':
            return Attendance.objects.filter(lesson__course__teacher=user)
        return Attendance.objects.filter(student=user)

    def create(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()

            # Проверка обязательных полей
            required_fields = ['lesson_id', 'student_id', 'is_present']
            for field in required_fields:
                if field not in request.data:
                    raise ValidationError(f"Поле '{field}' обязательно")

            # Проверка существования урока
            lesson_id = request.data.get('lesson_id')
            try:
                lesson = Lesson.objects.get(id=lesson_id)
                if lesson.course.teacher != request.user:
                    raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            except Lesson.DoesNotExist:
                raise ValidationError(f"Урок с ID {lesson_id} не найден")

            # Проверка существования студента
            student_id = request.data.get('student_id')
            try:
                student = User.objects.get(id=student_id, role='student')
                # Проверка, что студент записан на курс через группу
                if not student.student_groups.filter(courses=lesson.course).exists():
                    raise ValidationError("Студент не записан на данный курс")
            except User.DoesNotExist:
                raise ValidationError(f"Студент с ID {student_id} не найден")

            # Проверка, что посещаемость еще не отмечена
            if Attendance.objects.filter(lesson=lesson, student=student).exists():
                raise ValidationError("Посещаемость для этого студента уже отмечена")

            # Создание записи посещаемости
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

    def check_teacher_permission(self):
        if self.request.user.role != 'teacher':
            raise PermissionDenied("Только преподаватели могут управлять оценками")

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):  # Проверка для swagger
            return Grade.objects.none()
            
        user = self.request.user
        if user.role == 'teacher':
            return Grade.objects.all()
        return Grade.objects.filter(student=user)

    def get_object(self):
        obj = super().get_object()
        if self.request.user.role == 'teacher' and obj.lesson.course.teacher != self.request.user:
            raise PermissionDenied("Вы не являетесь преподавателем этого курса")
        return obj

    def create(self, request, *args, **kwargs):
        try:
            self.check_teacher_permission()

            # Проверка обязательных полей
            required_fields = ['lesson_id', 'student_id', 'value']
            for field in required_fields:
                if field not in request.data:
                    return Response({'error': f"Поле '{field}' обязательно"}, status=status.HTTP_400_BAD_REQUEST)

            # Проверка существования урока
            lesson_id = request.data.get('lesson_id')
            try:
                lesson = Lesson.objects.get(id=lesson_id)
                if lesson.course.teacher != request.user:
                    raise PermissionDenied("Вы не являетесь преподавателем этого курса")
            except Lesson.DoesNotExist:
                raise ValidationError(f"Урок с ID {lesson_id} не найден")

            # Проверка существования студента
            student_id = request.data.get('student_id')
            try:
                student = User.objects.get(id=student_id, role='student')
                # Проверка, что студент записан на курс через группу
                if not Group.objects.filter(students=student, courses=lesson.course).exists():
                    raise ValidationError("Студент не записан на данный курс")
            except User.DoesNotExist:
                raise ValidationError(f"Студент с ID {student_id} не найден")

            # Проверка значения оценки
            value = request.data.get('value')
            if not isinstance(value, (int, float)) or value < 0 or value > 100:
                raise ValidationError("Оценка должна быть числом от 0 до 100")

            # Проверка, что оценка еще не выставлена
            if Grade.objects.filter(lesson=lesson, student=student).exists():
                raise ValidationError("Оценка для этого студента уже выставлена")

            # Создание оценки
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='my-grades')
    def my_grades(self, request):
        if request.user.role != 'student':
            raise PermissionDenied("Только студенты могут просматривать свои оценки")
        grades = Grade.objects.filter(student=request.user)
        serializer = self.get_serializer(grades, many=True)
        return Response(serializer.data)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer