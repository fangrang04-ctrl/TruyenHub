from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from novels.import_views import (
    start_import,
    import_status,
)

from novels.views import (
    home,
    search_novels,
    category_list,
    category_detail,
    novel_detail,
    chapter_detail,
    new_novels,
    completed_novels,
    login_view,
    register_view,
    account_view,
    password_change_view,
    logout_view,
    toggle_follow,
    followed_novels,
    import_novel,
)


urlpatterns = [
    path(
        'admin/',
        admin.site.urls
    ),

    path(
        '',
        home,
        name='home'
    ),

    path(
        'tim-kiem/',
        search_novels,
        name='search_novels'
    ),

    path(
        'import-truyen/bat-dau/',
        start_import,
        name='start_import'
    ),

    path(
        'import-truyen/',
        import_novel,
        name='import_novel'
    ),

    path(
        'import-truyen/tien-do/',
        import_status,
        name='import_status'
    ),

    path(
        'the-loai/',
        category_list,
        name='category_list'
    ),

    path(
        'the-loai/<int:category_id>/',
        category_detail,
        name='category_detail'
    ),

    path(
        'truyen-moi/',
        new_novels,
        name='new_novels'
    ),

    path(
        'truyen-hoan-thanh/',
        completed_novels,
        name='completed_novels'
    ),

    path(
        'dang-nhap/',
        login_view,
        name='login'
    ),

    path(
        'dang-ky/',
        register_view,
        name='register'
    ),

    path(
        'tai-khoan/',
        account_view,
        name='account'
    ),

    path(
        'tai-khoan/doi-mat-khau/',
        password_change_view,
        name='password_change'
    ),

    path(
        'dang-xuat/',
        logout_view,
        name='logout'
    ),

    path(
        'truyen-dang-theo-doi/',
        followed_novels,
        name='followed_novels'
    ),

    path(
        'truyen/<int:novel_id>/theo-doi/',
        toggle_follow,
        name='toggle_follow'
    ),

    path(
        'truyen/<int:novel_id>/',
        novel_detail,
        name='novel_detail'
    ),

    path(
        'truyen/<int:novel_id>/chuong/<int:chapter_number>/',
        chapter_detail,
        name='chapter_detail'
    ),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )