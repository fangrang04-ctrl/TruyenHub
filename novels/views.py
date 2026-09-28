import unicodedata
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
    LoginForm,
    NovelImportForm,
    RegisterForm,
    UserPasswordChangeForm,
)
from .models import (
    Category,
    Chapter,
    FollowedNovel,
    Novel,
    ReadingHistory,
)


def home(request):
    novels = Novel.objects.filter(
        status='published'
    ).prefetch_related(
        'categories'
    ).order_by(
        '-created_at'
    )

    categories = Category.objects.all().order_by(
        'name'
    )

    featured_novel = novels.first()

    reading_history = []

    if request.user.is_authenticated:
        reading_history = ReadingHistory.objects.filter(
            user=request.user
        ).select_related(
            'novel',
            'chapter'
        ).prefetch_related(
            'novel__categories'
        )[:6]

    return render(
        request,
        'novels/home.html',
        {
            'novels': novels,
            'categories': categories,
            'featured_novel': featured_novel,
            'reading_history': reading_history,
        }
    )


def remove_accents(value):
    value = unicodedata.normalize(
        'NFD',
        value
    )

    value = ''.join(
        char
        for char in value
        if unicodedata.category(char) != 'Mn'
    )

    return value.replace(
        'Đ',
        'D'
    ).replace(
        'đ',
        'd'
    )


def search_novels(request):
    query = request.GET.get(
        'q',
        ''
    ).strip()

    category_id = request.GET.get(
        'category',
        ''
    ).strip()

    novels = Novel.objects.filter(
        status='published'
    ).annotate(
        chapter_count=Count(
            'chapters'
        )
    ).prefetch_related(
        'categories'
    ).order_by(
        '-created_at'
    )

    categories = Category.objects.all().order_by(
        'name'
    )

    selected_category = None

    if category_id:
        selected_category = get_object_or_404(
            Category,
            id=category_id
        )

        novels = novels.filter(
            categories=selected_category
        )

    if query:
        normalized_query = remove_accents(
            query
        ).lower()

        matched_novels = []

        for novel in novels:
            title = remove_accents(
                novel.title or ''
            ).lower()

            author = remove_accents(
                novel.author or ''
            ).lower()

            if (
                normalized_query in title
                or normalized_query in author
            ):
                matched_novels.append(
                    novel
                )

        novels = matched_novels

    return render(
        request,
        'novels/search.html',
        {
            'novels': novels,
            'categories': categories,
            'query': query,
            'selected_category': selected_category,
        }
    )


def category_list(request):
    categories = Category.objects.all().order_by(
        'name'
    )

    return render(
        request,
        'novels/category_list.html',
        {
            'categories': categories,
        }
    )


def category_detail(request, category_id):
    category = get_object_or_404(
        Category,
        id=category_id
    )

    novels = Novel.objects.filter(
        status='published',
        categories=category
    ).annotate(
        chapter_count=Count(
            'chapters'
        )
    ).prefetch_related(
        'categories'
    ).order_by(
        '-created_at'
    )

    return render(
        request,
        'novels/category_detail.html',
        {
            'category': category,
            'novels': novels,
        }
    )


def novel_detail(request, novel_id):
    novel = get_object_or_404(
        Novel.objects.prefetch_related(
            'categories',
            'chapters'
        ),
        id=novel_id,
        status='published'
    )

    chapters = novel.chapters.filter(
        status='published'
    ).order_by(
        'chapter_number'
    )

    is_following = False

    if request.user.is_authenticated:
        is_following = FollowedNovel.objects.filter(
            user=request.user,
            novel=novel
        ).exists()

    return render(
        request,
        'novels/novel_detail.html',
        {
            'novel': novel,
            'chapters': chapters,
            'is_following': is_following,
        }
    )


@login_required
def chapter_detail(
    request,
    novel_id,
    chapter_number
):
    novel = get_object_or_404(
        Novel,
        id=novel_id,
        status='published'
    )

    chapter = get_object_or_404(
        Chapter,
        novel=novel,
        chapter_number=chapter_number,
        status='published'
    )

    previous_chapter = Chapter.objects.filter(
        novel=novel,
        chapter_number__lt=chapter.chapter_number,
        status='published'
    ).order_by(
        '-chapter_number'
    ).first()

    next_chapter = Chapter.objects.filter(
        novel=novel,
        chapter_number__gt=chapter.chapter_number,
        status='published'
    ).order_by(
        'chapter_number'
    ).first()

    ReadingHistory.objects.update_or_create(
        user=request.user,
        novel=novel,
        defaults={
            'chapter': chapter
        }
    )

    return render(
        request,
        'novels/chapter_detail.html',
        {
            'novel': novel,
            'chapter': chapter,
            'previous_chapter': previous_chapter,
            'next_chapter': next_chapter,
        }
    )


def new_novels(request):
    novels = Novel.objects.filter(
        status='published'
    ).prefetch_related(
        'categories'
    ).order_by(
        '-created_at'
    )

    return render(
        request,
        'novels/new_novels.html',
        {
            'novels': novels,
        }
    )


def completed_novels(request):
    novels = Novel.objects.filter(
        status='published',
        is_completed=True
    ).prefetch_related(
        'categories'
    ).order_by(
        '-created_at'
    )

    return render(
        request,
        'novels/completed_novels.html',
        {
            'novels': novels,
        }
    )


def login_view(request):
    if request.user.is_authenticated:
        return redirect(
            'account'
        )

    if request.method == 'POST':
        form = LoginForm(
            request.POST
        )

        if form.is_valid():
            username = form.cleaned_data[
                'username'
            ]

            password = form.cleaned_data[
                'password'
            ]

            user = authenticate(
                request,
                username=username,
                password=password
            )

            if user is not None:
                login(
                    request,
                    user
                )

                next_url = request.POST.get(
                    'next'
                )

                if next_url:
                    return redirect(
                        next_url
                    )

                return redirect(
                    'home'
                )

            form.add_error(
                None,
                'Tên tài khoản hoặc mật khẩu không đúng.'
            )
    else:
        form = LoginForm()

    return render(
        request,
        'novels/login.html',
        {
            'form': form,
            'next': request.GET.get(
                'next',
                ''
            ),
        }
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect(
            'account'
        )

    if request.method == 'POST':
        form = RegisterForm(
            request.POST
        )

        if form.is_valid():
            user = form.save()

            login(
                request,
                user
            )

            return redirect(
                'home'
            )
    else:
        form = RegisterForm()

    return render(
        request,
        'novels/register.html',
        {
            'form': form,
        }
    )


@login_required
def account_view(request):
    followed = FollowedNovel.objects.filter(
        user=request.user,
        novel__status='published'
    ).select_related(
        'novel'
    ).prefetch_related(
        'novel__categories'
    ).order_by(
        '-created_at'
    )

    history = ReadingHistory.objects.filter(
        user=request.user
    ).select_related(
        'novel',
        'chapter'
    ).prefetch_related(
        'novel__categories'
    ).order_by(
        '-last_read_at'
    )

    return render(
        request,
        'novels/account.html',
        {
            'followed': followed,
            'history': history,
            'followed_count': followed.count(),
            'history_count': history.count(),
        }
    )


@login_required
def password_change_view(request):
    if request.method == 'POST':
        form = UserPasswordChangeForm(
            request.user,
            request.POST
        )

        if form.is_valid():
            user = form.save()

            update_session_auth_hash(
                request,
                user
            )

            return redirect(
                'account'
            )
    else:
        form = UserPasswordChangeForm(
            request.user
        )

    return render(
        request,
        'novels/password_change.html',
        {
            'form': form,
        }
    )


@login_required
def logout_view(request):
    logout(
        request
    )

    return redirect(
        'home'
    )


@login_required
def toggle_follow(
    request,
    novel_id
):
    novel = get_object_or_404(
        Novel,
        id=novel_id,
        status='published'
    )

    if request.method == 'POST':
        followed = FollowedNovel.objects.filter(
            user=request.user,
            novel=novel
        )

        if followed.exists():
            followed.delete()
        else:
            FollowedNovel.objects.create(
                user=request.user,
                novel=novel
            )

    return redirect(
        'novel_detail',
        novel_id=novel.id
    )


@login_required
def followed_novels(request):
    followed = FollowedNovel.objects.filter(
        user=request.user,
        novel__status='published'
    ).select_related(
        'novel'
    ).prefetch_related(
        'novel__categories'
    ).order_by(
        '-created_at'
    )

    return render(
        request,
        'novels/followed_novels.html',
        {
            'followed': followed,
        }
    )


def save_novel_categories(
    novel,
    category_names
):
    novel.categories.clear()

    for category_name in category_names:
        category_name = category_name.strip()

        if not category_name:
            continue

        category, created = Category.objects.get_or_create(
            name=category_name
        )

        novel.categories.add(
            category
        )


def download_cover(
    novel,
    cover_url
):
    if not cover_url:
        return

    if novel.cover:
        try:
            if novel.cover.storage.exists(
                novel.cover.name
            ):
                return
        except Exception:
            pass

        novel.cover.delete(
            save=False
        )

    request_image = Request(
        cover_url,
        headers={
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/153.0.0.0 Safari/537.36'
            ),
            'Accept': (
                'image/avif,image/webp,image/apng,image/svg+xml,'
                'image/*,*/*;q=0.8'
            ),
            'Referer': 'https://www.metruyenchu.com/',
        }
    )

    with urlopen(
        request_image,
        timeout=30
    ) as image_response:
        image_data = image_response.read()
        content_type = image_response.headers.get(
            'Content-Type',
            ''
        ).lower()

    if not image_data:
        raise ValueError(
            'Ảnh bìa tải về bị rỗng.'
        )

    if (
        'image' not in content_type
        and not image_data.startswith(
            (
                b'\xff\xd8\xff',
                b'\x89PNG',
                b'GIF8',
                b'RIFF'
            )
        )
    ):
        raise ValueError(
            'URL ảnh bìa không trả về dữ liệu hình ảnh hợp lệ.'
        )

    parsed_url = urlparse(
        cover_url
    )

    filename = parsed_url.path.rsplit(
        '/',
        1
    )[-1].split(
        '?',
        1
    )[0]

    if not filename:
        filename = f'novel_{novel.id}.jpg'

    if '.' not in filename:
        extension = '.jpg'

        if 'png' in content_type:
            extension = '.png'
        elif 'webp' in content_type:
            extension = '.webp'
        elif 'gif' in content_type:
            extension = '.gif'

        filename += extension

    novel.cover.save(
        filename,
        ContentFile(
            image_data
        ),
        save=True
    )

def create_or_update_imported_novel(
    source_url,
    imported_data,
    user
):
    novel = Novel.objects.filter(
        source_url=source_url
    ).first()

    if novel is None:
        novel = Novel.objects.create(
            title=imported_data.get(
                'title',
                ''
            ),
            author=imported_data.get(
                'author',
                ''
            ),
            description=imported_data.get(
                'description',
                ''
            ),
            source_url=source_url,
            uploader=user,
            status='published',
            is_completed=False,
        )
    else:
        novel.title = imported_data.get(
            'title',
            novel.title
        )

        novel.author = imported_data.get(
            'author',
            novel.author
        )

        novel.description = imported_data.get(
            'description',
            novel.description
        )

        if not novel.uploader:
            novel.uploader = user

        novel.status = 'published'

        novel.save()

    save_novel_categories(
        novel,
        imported_data.get(
            'categories',
            []
        )
    )

    download_cover(
        novel,
        imported_data.get(
            'cover',
            ''
        )
    )

    return novel


@login_required
def import_novel(request):
    form = NovelImportForm()

    imported_data = None
    imported_novel = None
    chapter_list = []
    error_message = None
    success_message = None

    if request.method == 'POST':
        form = NovelImportForm(
            request.POST
        )

        if form.is_valid():
            source_url = form.cleaned_data[
                'source_url'
            ]

            action = request.POST.get(
                'action',
                ''
            )

            try:
                from .importers.mtc import (
                    fetch_mtc_chapter,
                    fetch_mtc_chapters,
                    fetch_mtc_novel,
                )

                imported_data = fetch_mtc_novel(
                    source_url
                )

                if action == 'save_novel':
                    imported_novel = (
                        create_or_update_imported_novel(
                            source_url,
                            imported_data,
                            request.user
                        )
                    )

                    chapter_list = fetch_mtc_chapters(
                        source_url
                    )

                    success_message = (
                        'Đã nhập thông tin truyện vào TruyenHub.'
                    )

                elif action in [
                    'load_chapters',
                    'import_one',
                    'import_range',
                    'import_all',
                ]:
                    imported_novel = Novel.objects.filter(
                        source_url=source_url
                    ).first()

                    if imported_novel is None:
                        imported_novel = (
                            create_or_update_imported_novel(
                                source_url,
                                imported_data,
                                request.user
                            )
                        )

                    chapter_list = fetch_mtc_chapters(
                        source_url
                    )

                    if action == 'load_chapters':
                        success_message = (
                            f'Đã tìm thấy {len(chapter_list)} chương.'
                        )

                    else:
                        selected_numbers = []

                        if action == 'import_one':
                            chapter_number = (
                                form.cleaned_data.get(
                                    'chapter_number'
                                )
                            )

                            if not chapter_number:
                                raise ValueError(
                                    'Hãy nhập số chương cần lấy.'
                                )

                            selected_numbers = [
                                chapter_number
                            ]

                        elif action == 'import_range':
                            chapter_start = (
                                form.cleaned_data.get(
                                    'chapter_start'
                                )
                            )

                            chapter_end = (
                                form.cleaned_data.get(
                                    'chapter_end'
                                )
                            )

                            if not chapter_start or not chapter_end:
                                raise ValueError(
                                    'Hãy nhập chương bắt đầu và chương kết thúc.'
                                )

                            if chapter_start > chapter_end:
                                raise ValueError(
                                    'Chương bắt đầu không được lớn hơn chương kết thúc.'
                                )

                            selected_numbers = list(
                                range(
                                    chapter_start,
                                    chapter_end + 1
                                )
                            )

                        elif action == 'import_all':
                            selected_numbers = [
                                item['number']
                                for item in chapter_list
                            ]

                        chapter_map = {
                            item['number']: item
                            for item in chapter_list
                        }

                        missing_numbers = [
                            number
                            for number in selected_numbers
                            if number not in chapter_map
                        ]

                        if missing_numbers:
                            preview_missing = ', '.join(
                                str(number)
                                for number in missing_numbers[:20]
                            )

                            if len(missing_numbers) > 20:
                                preview_missing += '...'

                            raise ValueError(
                                'Không tìm thấy chương: '
                                + preview_missing
                            )

                        imported_count = 0

                        for number in selected_numbers:
                            source_chapter = chapter_map[
                                number
                            ]

                            chapter_data = fetch_mtc_chapter(
                                source_chapter['url']
                            )

                            Chapter.objects.update_or_create(
                                novel=imported_novel,
                                chapter_number=number,
                                defaults={
                                    'title': chapter_data.get(
                                        'title'
                                    ) or source_chapter.get(
                                        'name',
                                        f'Chương {number}'
                                    ),
                                    'content': chapter_data.get(
                                        'content',
                                        ''
                                    ),
                                    'status': 'published',
                                }
                            )

                            imported_count += 1

                        success_message = (
                            f'Đã import {imported_count} chương.'
                        )

            except Exception as error:
                error_message = str(
                    error
                )

    if imported_novel:
        existing_numbers = set(
            imported_novel.chapters.values_list(
                'chapter_number',
                flat=True
            )
        )

        for item in chapter_list:
            item['imported'] = (
                item['number'] in existing_numbers
            )

    return render(
        request,
        'novels/import_novel.html',
        {
            'form': form,
            'imported_data': imported_data,
            'imported_novel': imported_novel,
            'chapter_list': chapter_list,
            'error_message': error_message,
            'success_message': success_message,
        }
    )