from django.contrib import admin
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Category, Novel, Chapter


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display = (
        'name',
    )

    search_fields = (
        'name',
    )


@admin.register(Novel)
class NovelAdmin(admin.ModelAdmin):

    list_display = (
        'title',
        'author',
        'status',
        'uploader',
        'chapter_count',
        'chapter_actions',
        'created_at',
    )

    list_filter = (
        'status',
        'categories',
    )

    search_fields = (
        'title',
        'author',
    )

    filter_horizontal = (
        'categories',
    )

    readonly_fields = (
        'chapter_count',
    )

    actions = (
        'delete_selected',
    )

    change_list_template = 'admin/novels/novel/change_list.html'

    def chapter_count(self, obj):
        return obj.chapters.count()

    chapter_count.short_description = 'Số chương'

    def chapter_actions(self, obj):

        manage_url = reverse(
            'admin:novels_novel_manage_chapters',
            args=[obj.pk]
        )

        add_url = reverse(
            'admin:novels_novel_add_chapter',
            args=[obj.pk]
        )

        return format_html(
            '<a class="novel-action novel-action-manage" href="{}">'
            '📚 Quản lý chương'
            '</a>'
            '<a class="novel-action novel-action-add" href="{}">'
            '＋ Thêm chương'
            '</a>',
            manage_url,
            add_url,
        )

    chapter_actions.short_description = 'Chương'

    def delete_queryset(self, request, queryset):

        novels = list(queryset)

        for novel in novels:

            if novel.cover:
                try:
                    novel.cover.delete(
                        save=False
                    )
                except Exception:
                    pass

        queryset.delete()

    def get_urls(self):

        urls = super().get_urls()

        custom_urls = [

            path(
                '<path:object_id>/chapters/',
                self.admin_site.admin_view(
                    self.manage_chapters
                ),
                name='novels_novel_manage_chapters',
            ),

            path(
                '<path:object_id>/chapters/add/',
                self.admin_site.admin_view(
                    self.add_chapter
                ),
                name='novels_novel_add_chapter',
            ),

            path(
                '<path:object_id>/chapters/<int:chapter_id>/edit/',
                self.admin_site.admin_view(
                    self.edit_chapter
                ),
                name='novels_novel_edit_chapter',
            ),

            path(
                '<path:object_id>/chapters/<int:chapter_id>/delete/',
                self.admin_site.admin_view(
                    self.delete_chapter
                ),
                name='novels_novel_delete_chapter',
            ),
        ]

        return custom_urls + urls

    def get_novel(self, object_id):

        try:
            return Novel.objects.get(pk=object_id)
        except Novel.DoesNotExist:
            return None

    def manage_chapters(self, request, object_id):

        novel = self.get_novel(object_id)

        if novel is None:
            return HttpResponseRedirect(
                reverse('admin:novels_novel_changelist')
            )

        chapters = novel.chapters.all().order_by(
            'chapter_number'
        )

        context = {
            **self.admin_site.each_context(request),
            'title': f'Quản lý chương - {novel.title}',
            'novel': novel,
            'chapters': chapters,
            'opts': self.model._meta,
        }

        return TemplateResponse(
            request,
            'admin/novels/chapter_list.html',
            context,
        )

    def add_chapter(self, request, object_id):

        novel = self.get_novel(object_id)

        if novel is None:
            return HttpResponseRedirect(
                reverse('admin:novels_novel_changelist')
            )

        from .forms import ChapterAdminForm

        if request.method == 'POST':

            form = ChapterAdminForm(
                request.POST
            )

            if form.is_valid():

                chapter = form.save(
                    commit=False
                )

                chapter.novel = novel
                chapter.save()

                self.message_user(
                    request,
                    f'Đã thêm Chương {chapter.chapter_number}.',
                )

                return HttpResponseRedirect(
                    reverse(
                        'admin:novels_novel_manage_chapters',
                        args=[novel.pk]
                    )
                )

        else:

            next_number = (
                novel.chapters.order_by(
                    '-chapter_number'
                )
                .values_list(
                    'chapter_number',
                    flat=True
                )
                .first()
                or 0
            ) + 1

            form = ChapterAdminForm(
                initial={
                    'chapter_number': next_number,
                    'status': 'draft',
                }
            )

        context = {
            **self.admin_site.each_context(request),
            'title': f'Thêm chương - {novel.title}',
            'novel': novel,
            'form': form,
            'is_edit': False,
            'opts': self.model._meta,
        }

        return TemplateResponse(
            request,
            'admin/novels/chapter_editor.html',
            context,
        )

    def edit_chapter(
        self,
        request,
        object_id,
        chapter_id
    ):

        novel = self.get_novel(object_id)

        if novel is None:
            return HttpResponseRedirect(
                reverse('admin:novels_novel_changelist')
            )

        try:

            chapter = novel.chapters.get(
                pk=chapter_id
            )

        except Chapter.DoesNotExist:

            return HttpResponseRedirect(
                reverse(
                    'admin:novels_novel_manage_chapters',
                    args=[novel.pk]
                )
            )

        from .forms import ChapterAdminForm

        if request.method == 'POST':

            form = ChapterAdminForm(
                request.POST,
                instance=chapter
            )

            if form.is_valid():

                chapter = form.save()

                self.message_user(
                    request,
                    f'Đã lưu Chương {chapter.chapter_number}.',
                )

                return HttpResponseRedirect(
                    reverse(
                        'admin:novels_novel_manage_chapters',
                        args=[novel.pk]
                    )
                )

        else:

            form = ChapterAdminForm(
                instance=chapter
            )

        context = {
            **self.admin_site.each_context(request),
            'title': (
                f'Sửa Chương {chapter.chapter_number}'
                f' - {novel.title}'
            ),
            'novel': novel,
            'chapter': chapter,
            'form': form,
            'is_edit': True,
            'opts': self.model._meta,
        }

        return TemplateResponse(
            request,
            'admin/novels/chapter_editor.html',
            context,
        )

    def delete_chapter(
        self,
        request,
        object_id,
        chapter_id
    ):

        novel = self.get_novel(object_id)

        if novel is None:
            return HttpResponseRedirect(
                reverse('admin:novels_novel_changelist')
            )

        try:

            chapter = novel.chapters.get(
                pk=chapter_id
            )

        except Chapter.DoesNotExist:

            return HttpResponseRedirect(
                reverse(
                    'admin:novels_novel_manage_chapters',
                    args=[novel.pk]
                )
            )

        if request.method == 'POST':

            chapter_number = chapter.chapter_number

            chapter.delete()

            self.message_user(
                request,
                f'Đã xóa Chương {chapter_number}.',
                level='SUCCESS',
            )

            return HttpResponseRedirect(
                reverse(
                    'admin:novels_novel_manage_chapters',
                    args=[novel.pk]
                )
            )

        context = {
            **self.admin_site.each_context(request),
            'title': 'Xác nhận xóa chương',
            'novel': novel,
            'chapter': chapter,
            'opts': self.model._meta,
        }

        return TemplateResponse(
            request,
            'admin/novels/chapter_delete.html',
            context,
        )