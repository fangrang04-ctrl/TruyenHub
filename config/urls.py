from django.contrib import admin
from django.urls import path

from novels.import_views import (
    import_novel,
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
)


urlpatterns = [
    # =========================
    # ADMIN
    # =========================
    path(
        'admin/',
        admin.site.urls
    ),

    # =========================
    # TRANG CHỦ
    # =========================
    path(
        '',
        home,
        name='home'
    ),

    # =========================
    # TÌM KIẾM
    # =========================
    path(
        'tim-kiem/',
        search_novels,
        name='search_novels'
    ),

    # =========================
    # THỂ LOẠI
    # =========================
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

    # =========================
    # TRUYỆN
    # =========================
    path(
        'truyen/<int:novel_id>/',
        novel_detail,
        name='novel_detail'
    ),

    # =========================
    # ĐỌC CHƯƠNG
    # =========================
    path(
        'truyen/<int:novel_id>/chuong/<int:chapter_number>/',
        chapter_detail,
        name='chapter_detail'
    ),

    # =========================
    # DANH SÁCH TRUYỆN
    # =========================
    path(
        'truyen-moi/',
        new_novels,
        name='new_novels'
    ),

    path(
        'truyen-hoan/',
        completed_novels,
        name='completed_novels'
    ),

    # =========================
    # TÀI KHOẢN
    # =========================
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
        'doi-mat-khau/',
        password_change_view,
        name='password_change'
    ),

    path(
        'dang-xuat/',
        logout_view,
        name='logout'
    ),

    # =========================
    # THEO DÕI TRUYỆN
    # =========================
    path(
        'truyen/<int:novel_id>/theo-doi/',
        toggle_follow,
        name='toggle_follow'
    ),

    path(
        'truyen-theo-doi/',
        followed_novels,
        name='followed_novels'
    ),

    # =========================
    # IMPORT TRUYỆN
    # =========================
    #
    # QUAN TRỌNG:
    # import_novel ở đây lấy từ
    # novels.import_views
    #
    # Không lấy import_novel từ novels.views
    #
    path(
        'import-truyen/',
        import_novel,
        name='import_novel'
    ),

    # Bắt đầu job import nền
    path(
        'import-truyen/bat-dau/',
        start_import,
        name='start_import'
    ),

    # Kiểm tra tiến độ import
    path(
        'import-truyen/tien-do/',
        import_status,
        name='import_status'
    ),
]