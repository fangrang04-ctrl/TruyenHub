from django.db import models
from django.contrib.auth.models import User


class Category(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    def __str__(self):
        return self.name


class Novel(models.Model):

    STATUS_CHOICES = [
        ('draft', 'Bản nháp'),
        ('pending', 'Chờ duyệt'),
        ('published', 'Đã xuất bản'),
        ('rejected', 'Từ chối'),
    ]

    title = models.CharField(
        max_length=255
    )

    author = models.CharField(
        max_length=255
    )

    cover = models.ImageField(
        upload_to='novels/covers/',
        blank=True,
        null=True
    )

    description = models.TextField(
        blank=True
    )

  
    source_url = models.URLField(
    max_length=500,
    blank=True,
    null=True
)

    uploader = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_novels'
    )

    categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name='novels'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    is_completed = models.BooleanField(
        default=False,
        verbose_name='Đã hoàn thành'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.title


class Chapter(models.Model):

    STATUS_CHOICES = [
        ('draft', 'Bản nháp'),
        ('pending', 'Chờ duyệt'),
        ('published', 'Đã xuất bản'),
        ('rejected', 'Từ chối'),
    ]

    novel = models.ForeignKey(
        Novel,
        on_delete=models.CASCADE,
        related_name='chapters'
    )

    chapter_number = models.PositiveIntegerField()

    title = models.CharField(
        max_length=255
    )

    content = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['chapter_number']
        constraints = [
            models.UniqueConstraint(
                fields=['novel', 'chapter_number'],
                name='unique_chapter_number_per_novel'
            )
        ]

    def __str__(self):
        return f'{self.novel.title} - Chương {self.chapter_number}'


class ReadingHistory(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reading_history'
    )

    novel = models.ForeignKey(
        Novel,
        on_delete=models.CASCADE,
        related_name='reading_history'
    )

    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name='reading_history'
    )

    last_read_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['-last_read_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'novel'],
                name='unique_reading_history_per_user_novel'
            )
        ]

    def __str__(self):
        return f'{self.user.username} - {self.novel.title}'


class FollowedNovel(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='followed_novels'
    )

    novel = models.ForeignKey(
        Novel,
        on_delete=models.CASCADE,
        related_name='followers'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'novel'],
                name='unique_followed_novel_per_user'
            )
        ]

    def __str__(self):
        return f'{self.user.username} - {self.novel.title}'