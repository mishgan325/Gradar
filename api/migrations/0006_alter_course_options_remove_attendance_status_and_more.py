# Generated by Django 5.0.2 on 2025-05-14 22:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_alter_course_options'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='course',
            options={'verbose_name': 'Курс', 'verbose_name_plural': 'Курсы'},
        ),
        migrations.RemoveField(
            model_name='attendance',
            name='status',
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='end_time',
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='start_time',
        ),
        migrations.RemoveField(
            model_name='lesson',
            name='title',
        ),
        migrations.AddField(
            model_name='attendance',
            name='is_present',
            field=models.BooleanField(default=False, verbose_name='Присутствовал'),
        ),
        migrations.AddField(
            model_name='lesson',
            name='topic',
            field=models.CharField(default='-', max_length=200, verbose_name='Тема занятия'),
        ),
        migrations.AlterField(
            model_name='course',
            name='description',
            field=models.TextField(verbose_name='Описание'),
        ),
        migrations.AlterField(
            model_name='course',
            name='semester',
            field=models.CharField(choices=[('spring', 'Весна'), ('autumn', 'Осень')], max_length=6, verbose_name='Семестр'),
        ),
        migrations.AlterField(
            model_name='course',
            name='year',
            field=models.PositiveIntegerField(verbose_name='Учебный год'),
        ),
        migrations.AlterField(
            model_name='group',
            name='year',
            field=models.IntegerField(verbose_name='Год обучения'),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='date',
            field=models.DateTimeField(verbose_name='Дата и время'),
        ),
        migrations.AlterUniqueTogether(
            name='group',
            unique_together={('name', 'year')},
        ),
    ]
