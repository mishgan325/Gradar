from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

# Константы для семестров
SEMESTER_SPRING = 'spring'
SEMESTER_AUTUMN = 'autumn'
VALID_SEMESTER_VALUES = [SEMESTER_SPRING, SEMESTER_AUTUMN]
SEMESTER_CHOICES = [
    (SEMESTER_SPRING, 'Весна'),
    (SEMESTER_AUTUMN, 'Осень'),
]

class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('teacher', 'Teacher'),
    )
    
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='student'
    )
    email = models.EmailField(unique=True)
    bio = models.TextField(
        blank=True,
        verbose_name='Биография'
    )

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',
        blank=True,
    )

    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_permission_set',
        blank=True,
    )

    def is_teacher(self):
        return self.role == 'teacher'
    
    def is_student(self):
        return self.role == 'student'

    class Meta:
        ordering = ['id']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"


class Group(models.Model):
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Название группы'
    )
    year = models.IntegerField(
        verbose_name='Год обучения'
    )
    students = models.ManyToManyField(
        User,
        related_name='student_groups',
        limit_choices_to={'role': 'student'},
        verbose_name='Студенты'
    )

    class Meta:
        verbose_name = 'Группа'
        verbose_name_plural = 'Группы'
        unique_together = ['name', 'year']

    def __str__(self):
        return f"{self.name} ({self.year})"

    def validate_student(self, student):
        """Проверяет, что студент не состоит в другой группе"""
        if not student.is_student():
            raise ValidationError(f"Пользователь {student} не является студентом")
        
        other_groups = Group.objects.exclude(pk=self.pk if self.pk else None).filter(students=student)
        if other_groups.exists():
            raise ValidationError(
                f"Студент {student.get_full_name()} уже состоит в группе {other_groups.first().name}"
            )

    def clean(self):
        super().clean()
        # При создании группы students еще не доступны
        if self.pk:
            for student in self.students.all():
                self.validate_student(student)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Course(models.Model):
    name = models.CharField(
        max_length=200,
        verbose_name='Название курса'
    )
    description = models.TextField(
        verbose_name='Описание'
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='taught_courses',
        limit_choices_to={'role': 'teacher'},
        verbose_name='Преподаватель'
    )
    groups = models.ManyToManyField(
        'Group',
        related_name='courses',
        verbose_name='Группы'
    )
    semester = models.CharField(
        max_length=6,
        choices=SEMESTER_CHOICES,
        verbose_name='Семестр'
    )
    year = models.PositiveIntegerField(
        verbose_name='Учебный год'
    )

    class Meta:
        verbose_name = 'Курс'
        verbose_name_plural = 'Курсы'

    def __str__(self):
        return f"{self.name} ({self.get_semester_display()} {self.year})"


class Lesson(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name='Курс'
    )
    topic = models.CharField(
        max_length=200,
        verbose_name='Тема занятия',
        default='-'
    )
    date = models.DateTimeField(
        verbose_name='Дата и время'
    )

    class Meta:
        verbose_name = 'Занятие'
        verbose_name_plural = 'Занятия'
        ordering = ['-date']

    def __str__(self):
        return f"{self.course.name} — {self.topic} ({self.date:%d.%m.%Y})"


class Attendance(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name='Занятие'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='attendances',
        limit_choices_to={'role': 'student'},
        verbose_name='Студент'
    )
    is_present = models.BooleanField(
        default=False,
        verbose_name='Присутствовал'
    )

    class Meta:
        verbose_name = 'Посещаемость'
        verbose_name_plural = 'Посещаемость'
        unique_together = ('lesson', 'student')

    def __str__(self):
        status = "Присутствовал" if self.is_present else "Отсутствовал"
        return f"{self.student.get_full_name()} — {status} на {self.lesson}"


class Grade(models.Model):
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name='grades',
        verbose_name='Занятие'
    )
    student = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='grades',
        limit_choices_to={'role': 'student'},
        verbose_name='Студент'
    )
    value = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Оценка'
    )
    comment = models.TextField(
        blank=True,
        null=True,
        default='-',
        verbose_name='Комментарий'
    )

    class Meta:
        verbose_name = 'Оценка'
        verbose_name_plural = 'Оценки'
        unique_together = ('lesson', 'student')

    def __str__(self):
        return f"{self.student.get_full_name()} — {self.value} за {self.lesson.topic}"
