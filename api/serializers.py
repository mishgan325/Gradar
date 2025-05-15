from rest_framework import serializers
from .models import User, Course, Lesson, Attendance, Grade, Group
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'bio']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        token['role'] = user.role
        return token

class GroupSerializer(serializers.ModelSerializer):
    students = UserSerializer(many=True, read_only=True)
    student_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Group
        fields = ['id', 'name', 'year', 'students', 'student_ids']

    def validate_student_ids(self, value):
        if not value:
            return value
        
        # Verify all students exist and are actually students
        students = User.objects.filter(id__in=value)
        if len(students) != len(value):
            raise serializers.ValidationError("One or more student IDs are invalid")
        
        non_students = students.exclude(role='student')
        if non_students.exists():
            raise serializers.ValidationError(
                f"Users with IDs {list(non_students.values_list('id', flat=True))} are not students"
            )
        
        # Check if any student is already in another group
        for student in students:
            other_groups = Group.objects.exclude(pk=self.instance.pk if self.instance else None)
            other_groups = other_groups.filter(students=student)
            if other_groups.exists():
                raise serializers.ValidationError(
                    f"Student {student.get_full_name()} is already in group {other_groups.first().name}"
                )
        
        return value

    def create(self, validated_data):
        student_ids = validated_data.pop('student_ids', [])
        group = Group.objects.create(**validated_data)
        if student_ids:
            students = User.objects.filter(id__in=student_ids, role='student')
            group.students.set(students)
        return group

    def update(self, instance, validated_data):
        student_ids = validated_data.pop('student_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if student_ids is not None:
            students = User.objects.filter(id__in=student_ids, role='student')
            instance.students.set(students)
        return instance

class CourseSerializer(serializers.ModelSerializer):
    teacher = UserSerializer(read_only=True)
    groups = GroupSerializer(many=True, read_only=True)
    group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Course
        fields = ['id', 'name', 'description', 'semester', 'year', 'teacher', 'groups', 'group_ids']

    def validate_group_ids(self, value):
        if not value:
            return value
        
        # Verify all groups exist
        groups = Group.objects.filter(id__in=value)
        if len(groups) != len(value):
            raise serializers.ValidationError("One or more group IDs are invalid")
        return value

    def create(self, validated_data):
        group_ids = validated_data.pop('group_ids', [])
        course = Course.objects.create(**validated_data)
        
        if group_ids:
            groups = Group.objects.filter(id__in=group_ids)
            course.groups.set(groups)
        
        return course

    def update(self, instance, validated_data):
        group_ids = validated_data.pop('group_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if group_ids is not None:
            groups = Group.objects.filter(id__in=group_ids)
            instance.groups.set(groups)
        
        instance.save()
        return instance

class LessonSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    course_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Lesson
        fields = ['id', 'course', 'course_id', 'topic', 'date']

    def validate_course_id(self, value):
        try:
            course = Course.objects.get(id=value)
            # Проверяем, что текущий пользователь является преподавателем этого курса
            request = self.context.get('request')
            if request and request.user.is_authenticated:
                if course.teacher != request.user:
                    raise serializers.ValidationError("Вы не являетесь преподавателем этого курса")
            return value
        except Course.DoesNotExist:
            raise serializers.ValidationError("Указанный курс не существует")

    def validate_date(self, value):
        from datetime import datetime
        import pytz

        # Получаем текущее время в UTC
        now = datetime.now(pytz.UTC)
        
        # Если дата урока в прошлом
        if value < now:
            raise serializers.ValidationError("Дата урока не может быть в прошлом")
        
        return value

class AttendanceSerializer(serializers.ModelSerializer):
    lesson = LessonSerializer(read_only=True)
    student = UserSerializer(read_only=True)
    lesson_id = serializers.IntegerField(write_only=True)
    student_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'lesson', 'student', 'lesson_id', 'student_id', 'is_present']

    def validate(self, data):
        # При обновлении не требуем lesson_id и student_id
        if self.instance is not None:
            return data

        try:
            lesson = Lesson.objects.get(id=data['lesson_id'])
            student = User.objects.get(id=data['student_id'])
            
            # Проверяем, что студент записан на курс через группу
            if not student.student_groups.filter(courses=lesson.course).exists():
                raise serializers.ValidationError("Студент не записан на данный курс")
                
            data['lesson'] = lesson
            data['student'] = student
            return data
        except Lesson.DoesNotExist:
            raise serializers.ValidationError("Указанный урок не существует")
        except User.DoesNotExist:
            raise serializers.ValidationError("Указанный студент не существует")

    def create(self, validated_data):
        # Удаляем lesson_id и student_id, так как у нас уже есть объекты lesson и student
        validated_data.pop('lesson_id', None)
        validated_data.pop('student_id', None)
        return Attendance.objects.create(**validated_data)

    def update(self, instance, validated_data):
        if 'lesson_id' in validated_data:
            instance.lesson = Lesson.objects.get(id=validated_data.pop('lesson_id'))
        if 'student_id' in validated_data:
            instance.student = User.objects.get(id=validated_data.pop('student_id'))
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

class GradeSerializer(serializers.ModelSerializer):
    lesson = LessonSerializer(read_only=True)
    student = UserSerializer(read_only=True)
    lesson_id = serializers.IntegerField(write_only=True)
    student_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Grade
        fields = ['id', 'lesson', 'student', 'lesson_id', 'student_id', 'value', 'comment']

    def create(self, validated_data):
        lesson_id = validated_data.pop('lesson_id')
        student_id = validated_data.pop('student_id')
        lesson = Lesson.objects.get(id=lesson_id)
        student = User.objects.get(id=student_id)
        return Grade.objects.create(lesson=lesson, student=student, **validated_data)

    def update(self, instance, validated_data):
        if 'lesson_id' in validated_data:
            lesson_id = validated_data.pop('lesson_id')
            instance.lesson = Lesson.objects.get(id=lesson_id)
        if 'student_id' in validated_data:
            student_id = validated_data.pop('student_id')
            instance.student = User.objects.get(id=student_id)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
