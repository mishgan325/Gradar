from rest_framework import serializers
from .models import User, Course, Lesson, Attendance, Grade, Group
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password', 'role', 'first_name', 'last_name', 'bio')
        read_only_fields = ('id',)

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data.get('role', 'student'),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            bio=validated_data.get('bio', '')
        )
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = UserSerializer(self.user).data
        return data

class GroupSerializer(serializers.ModelSerializer):
    students = UserSerializer(many=True, read_only=True)
    student_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True,
        source='students'
    )

    class Meta:
        model = Group
        fields = ('id', 'name', 'students', 'student_ids')

    def create(self, validated_data):
        students = validated_data.pop('students', [])
        group = Group.objects.create(**validated_data)
        if students:
            group.students.set(students)
        return group

    def update(self, instance, validated_data):
        if 'students' in validated_data:
            instance.students.set(validated_data.pop('students'))
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance

class CourseSerializer(serializers.ModelSerializer):
    teacher = UserSerializer(read_only=True)
    groups = GroupSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = ('id', 'title', 'description', 'teacher', 'groups', 'semester', 'year')


class LessonSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    course_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Lesson
        fields = ('id', 'course', 'course_id', 'date', 'topic')

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


class AttendanceSerializer(serializers.ModelSerializer):
    lesson = LessonSerializer(read_only=True)
    student = UserSerializer(read_only=True)
    lesson_id = serializers.IntegerField(write_only=True)
    student_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Attendance
        fields = ('id', 'lesson', 'student', 'lesson_id', 'student_id', 'is_present')

    def validate(self, data):
        try:
            lesson = Lesson.objects.get(id=data['lesson_id'])
            student = User.objects.get(id=data['student_id'], role='student')
            
            # Проверяем, что студент записан на курс через группу
            if not student.student_groups.filter(courses=lesson.course).exists():
                raise serializers.ValidationError("Студент не записан на этот курс")
            
            # Проверяем, что отметка посещаемости еще не существует
            if Attendance.objects.filter(lesson=lesson, student=student).exists():
                raise serializers.ValidationError("Посещаемость для этого студента уже отмечена")
            
            # Добавляем объекты в validated_data для create/update
            data['lesson'] = lesson
            data['student'] = student
            return data
            
        except Lesson.DoesNotExist:
            raise serializers.ValidationError(f"Урок с ID {data.get('lesson_id')} не найден")
        except User.DoesNotExist:
            raise serializers.ValidationError(f"Студент с ID {data.get('student_id')} не найден")


class GradeSerializer(serializers.ModelSerializer):
    lesson = LessonSerializer(read_only=True)
    student = UserSerializer(read_only=True)

    class Meta:
        model = Grade
        fields = ('id', 'lesson', 'student', 'value', 'comment')
